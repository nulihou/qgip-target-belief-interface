import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv, GlobalAttention

class FiLMLayer(nn.Module):
    """
    Feature-wise Linear Modulation (FiLM) Layer.
    Injects query semantics into node features via affine transformation.
    gamma, beta = f(query)
    out = gamma * x + beta
    """
    def __init__(self, query_dim, feature_dim):
        super(FiLMLayer, self).__init__()
        self.fc = nn.Linear(query_dim, 2 * feature_dim)

    def forward(self, x, query):
        # x: [N, feature_dim]
        # query: [batch_size, query_dim]
        # Note: query needs to be broadcasted to N nodes
        
        # We assume query is already expanded or we handle batch mapping externally.
        # But in PyG batching, 'x' is [Total_N, D], and we need a 'batch' vector to map query.
        # For simplicity in this implementation, we assume the caller handles the broadcast
        # or passes a query vector that matches x's batch dimension (i.e. query[batch[i]]).
        
        params = self.fc(query) # [N, 2 * feature_dim]
        gamma, beta = torch.split(params, x.size(1), dim=1)
        
        return (1 + gamma) * x + beta

class GRUPlanningHead(nn.Module):
    def __init__(self, input_dim, hidden_dim=128, future_steps=80):
        super().__init__()
        self.future_steps = future_steps
        
        # 1. 状态编码器: 将 [context, ego_vel] 融合
        self.state_encoder = nn.Sequential(
            nn.Linear(input_dim + 2, hidden_dim), # +2 是因为注入了 vx, vy
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )
        
        # 2. GRU 核心: 负责时序推演
        self.gru = nn.GRUCell(hidden_dim, hidden_dim)
        
        # 3. 解码器: 输出这一步的位移 (dx, dy)
        self.decoder = nn.Linear(hidden_dim, 2)
        
    def forward(self, context_feat, ego_velocity):
        """
        context_feat: [B, D] 来自 GNN 的加权目标特征
        ego_velocity: [B, 2] Ego 当前速度向量
        """
        # 初始化
        batch_size = context_feat.size(0)
        
        # 初始输入融合
        state = torch.cat([context_feat, ego_velocity], dim=1)
        hx = self.state_encoder(state)
        
        predictions = []
        
        # 自回归生成
        for _ in range(self.future_steps):
            # GRU 更新隐藏状态
            hx = self.gru(hx, hx) # 简化版：Input=Hidden (Standard Autoregressive)
            
            # 预测这一步的位移 Delta
            delta = self.decoder(hx)
            predictions.append(delta)
            
        # 堆叠: [B, T, 2]
        pred_deltas = torch.stack(predictions, dim=1)
        return pred_deltas

class QGIPNet(nn.Module):
    """
    QGIP-Net: Query-Guided Interaction & Planning Network
    
    Architecture:
    1. Shared Backbone (FiLM-GNN): Extracts context-aware node features conditioned on query.
    2. Selection Head (MLP): Classifies which node is the target.
    3. Planning Head (GRU/MLP): Generates trajectory based on Soft-Attention context.
    """
    def __init__(self, node_dim=32, edge_dim=16, query_dim=5, hidden_dim=128, output_horizon=80):
        super(QGIPNet, self).__init__()
        
        # --- 1. Shared Backbone (FiLM-GNN) ---
        self.node_encoder = nn.Sequential(
            nn.Linear(node_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim)
        )
        
        self.edge_encoder = nn.Sequential(
            nn.Linear(edge_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim)
        )
        
        self.film1 = FiLMLayer(query_dim, hidden_dim)
        self.gnn1 = GATv2Conv(hidden_dim, hidden_dim, heads=4, concat=False, edge_dim=hidden_dim)
        
        self.film2 = FiLMLayer(query_dim, hidden_dim)
        self.gnn2 = GATv2Conv(hidden_dim, hidden_dim, heads=4, concat=False, edge_dim=hidden_dim)
        
        self.film3 = FiLMLayer(query_dim, hidden_dim)
        self.gnn3 = GATv2Conv(hidden_dim, hidden_dim, heads=4, concat=False, edge_dim=hidden_dim)

        # --- 2. Selection Head ---
        self.selection_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1) # Score for each node
        )
        
        # --- 3. Planning Head ---
        # Context Encoder: Fuses Ego + Weighted Target + Global Context
        self.global_pool = GlobalAttention(gate_nn=nn.Linear(hidden_dim, 1))
        
        self.planning_encoder = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim), # [Ego, Context, Global]
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )
        
        # Trajectory Decoder (GRU)
        # self.trajectory_gru = nn.GRU(hidden_dim, hidden_dim, batch_first=True)
        # self.trajectory_out = nn.Linear(hidden_dim, 2) # dx, dy per step
        
        # New GRU Planning Head
        self.planning_head = GRUPlanningHead(input_dim=hidden_dim * 3, hidden_dim=hidden_dim, future_steps=output_horizon)
        
        self.output_horizon = output_horizon

    def forward(self, x, edge_index, edge_attr, query, batch, ptr=None, ego_velocity=None):
        """
        Args:
            x: [Total_N, node_dim]
            edge_index: [2, Total_E]
            edge_attr: [Total_E, edge_dim]
            query: [Batch_Size, query_dim]
            batch: [Total_N] batch index for each node
            ptr: Optional, pointers for batch segmentation
            ego_velocity: [Batch_Size, 2] Optional, current velocity of ego vehicle
        
        Returns:
            selection_scores: [Total_N, 1] - Logits for selection
            pred_traj: [Batch_Size, T, 2] - Predicted trajectory
            aux_info: Dict containing attention weights etc.
        """
        
        # Runtime ablation flags used by the closed-loop CARLA runner.
        # `ablation_no_query` keeps the historical behavior used by older logs:
        # it removes query conditioning and edge conditioning together. The
        # finer-grained flags below are used for the component ablation suite.
        NO_QUERY = getattr(self, 'ablation_no_query', False) or getattr(self, 'ablation_query_zero', False)
        EDGE_OFF = getattr(self, 'ablation_edge_off', False) or getattr(self, 'ablation_no_query', False)
        FILM_OFF = getattr(self, 'ablation_film_off', False)

        if NO_QUERY:
            query = torch.zeros_like(query)
        if EDGE_OFF:
            edge_attr = torch.zeros_like(edge_attr)
        
        # --- A. Shared Backbone ---
        # 1. Expand query to node level for FiLM
        # query[batch] maps each node to its graph's query
        query_expanded = query[batch]
        
        h = self.node_encoder(x)
        e = self.edge_encoder(edge_attr)
        
        # Layer 1
        if not FILM_OFF:
            h = self.film1(h, query_expanded)
        h = self.gnn1(h, edge_index, edge_attr=e)
        h = F.relu(h)
        
        # Layer 2
        if not FILM_OFF:
            h = self.film2(h, query_expanded)
        h = self.gnn2(h, edge_index, edge_attr=e)
        h = F.relu(h)
        
        # Layer 3
        if not FILM_OFF:
            h = self.film3(h, query_expanded)
        h = self.gnn3(h, edge_index, edge_attr=e) # Final Node Embeddings [Total_N, hidden_dim]
        
        # --- B. Selection Head ---
        # Calculate scores for ALL nodes (candidates + anchors)
        # We will mask out non-candidates in the loss function
        selection_scores = self.selection_head(h) # [Total_N, 1]
        
        # --- C. Planning Head ---
        
        # 1. Soft Attention Conditioning
        # We need to compute "Context Feature" for each graph in the batch.
        # This is the weighted sum of all node features, weighted by their selection probability.
        # softmax should be applied per-graph.
        
        # Trick: Use softmax with scatter (from torch_scatter or manually with exponentials)
        # For simplicity/stability without extra deps, we iterate or use PyG utils if available.
        # Here is a manual implementation for clarity:
        
        # We only want to attend to candidates (masking is usually handled outside or by passing mask)
        # Assuming selection_scores are raw logits.
        # We need normalized probability P_i within each graph.
        
        # To do this efficiently in batch:
        # exp_scores = torch.exp(selection_scores)
        # sum_exp = scatter_add(exp_scores, batch)
        # probs = exp_scores / sum_exp[batch]
        
        # Using torch_geometric.utils.softmax
        from torch_geometric.utils import softmax
        probs = softmax(selection_scores, batch) # [Total_N, 1]
        
        # Weighted sum for context: h_context = sum(P_i * h_i)
        # global_add_pool does exactly sum pooling
        from torch_geometric.nn import global_add_pool
        h_context = global_add_pool(probs * h, batch) # [Batch_Size, hidden_dim]
        
        # 2. Ego Feature Extraction
        # We assume the first node of each graph is Ego (index 0 in local graph).
        # With 'ptr', ego indices are ptr[:-1].
        if ptr is not None:
            ego_indices = ptr[:-1]
        else:
            # Fallback: assume sorted batch index and take first occurrence
            # This is slow, better provide ptr
            # unique_batch, ego_indices = torch.unique(batch, return_inverse=False, sorted=True, return_counts=False)
            # Actually, usually node 0 is ego.
            # Let's assume the dataset puts ego first.
            # But in a batched tensor, we need global indices.
            # If ptr is [0, 5, 12], egos are at 0, 5.
            # If ptr is missing, we rely on the caller to handle this or we use scatter to find min index?
            # For now, let's assume ptr is passed (PyG DataLoader provides it).
            raise ValueError("ptr is required for identifying Ego node efficiently.")
            
        h_ego = h[ego_indices] # [Batch_Size, hidden_dim]
        
        # 3. Global Context
        h_global = self.global_pool(h, batch) # [Batch_Size, hidden_dim]
        
        # 4. Fusion & Decoding
        # Concatenate: [Ego, Weighted_Target, Global_Traffic]
        planning_input = torch.cat([h_ego, h_context, h_global], dim=1) # [Batch_Size, 3*hidden_dim]
        
        # Check ego_velocity
        if ego_velocity is None:
            # Fallback: assume zero velocity if not provided (not ideal for physics)
            ego_velocity = torch.zeros(planning_input.size(0), 2, device=planning_input.device)
            
        pred_traj = self.planning_head(planning_input, ego_velocity)
        
        return selection_scores, pred_traj, {'probs': probs}
