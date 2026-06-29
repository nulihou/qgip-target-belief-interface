import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, global_mean_pool
from lc_org_nav.baselines.end_to_end import EndToEndNet

class BaselineE2EAdapter(nn.Module):
    def __init__(self, vocab_size, color_num, type_num, rel_num, embed_dim=64):
        super(BaselineE2EAdapter, self).__init__()
        # Reuse embedding logic from BaselineGNN
        self.text_embed = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, embed_dim, batch_first=True)
        self.color_embed = nn.Embedding(color_num, embed_dim // 2)
        self.type_embed = nn.Embedding(type_num, embed_dim // 2)
        self.pos_mlp = nn.Linear(3, embed_dim)
        
        # EndToEndNet
        self.net = EndToEndNet(
            node_feat_dim=embed_dim,
            edge_feat_dim=0, # Ignored
            lang_feat_dim=embed_dim,
            hidden_dim=embed_dim,
            num_layers=3,
            num_rel_types=rel_num
        )

    def forward(self, data):
        # 1. Text
        batch_size = data.num_graphs
        text = data.text.view(batch_size, -1)
        text_emb = self.text_embed(text)
        _, (h_n, _) = self.lstm(text_emb)
        text_feat = h_n.squeeze(0) # [B, D]
        
        # 2. Nodes
        c_emb = self.color_embed(data.x_cat[:, 0])
        t_emb = self.type_embed(data.x_cat[:, 1])
        p_feat = self.pos_mlp(data.x_cont)
        node_feat = torch.cat([c_emb, t_emb], dim=1) + p_feat
        
        # 3. Candidate Mask
        candidate_mask = torch.ones(node_feat.size(0), device=node_feat.device)
        
        # 4. Forward
        # Handle batching: EndToEndNet expects single graph inputs in its current form
        # We assume batch_size=1 for evaluation
        if batch_size == 1:
            out = self.net(
                node_feats=node_feat,
                edge_index=None,
                edge_attr=None,
                lang_feat=text_feat[0],
                candidate_mask=candidate_mask
            )
            return out['goal_logits']
        else:
            # Simple loop for batch > 1 (inefficient but functional)
            logits_list = []
            start_idx = 0
            for i in range(batch_size):
                # Identify nodes belonging to graph i
                mask = (data.batch == i)
                n_feat = node_feat[mask]
                t_feat = text_feat[i]
                c_mask = candidate_mask[mask]
                
                out = self.net(
                    node_feats=n_feat,
                    edge_index=None,
                    edge_attr=None,
                    lang_feat=t_feat,
                    candidate_mask=c_mask
                )
                logits_list.append(out['goal_logits'])
            
            return torch.cat(logits_list, dim=0)

class BaselineGNN(nn.Module):
    def __init__(self, vocab_size, color_num, type_num, rel_num, embed_dim=64):
        super(BaselineGNN, self).__init__()
        
        # Text Encoder
        self.text_embed = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, embed_dim, batch_first=True)
        
        # Node Encoder
        self.color_embed = nn.Embedding(color_num, embed_dim // 2)
        self.type_embed = nn.Embedding(type_num, embed_dim // 2)
        self.pos_mlp = nn.Linear(3, embed_dim)
        
        # Edge Encoder
        self.edge_embed = nn.Embedding(rel_num, embed_dim)
        
        # GNN
        self.gnn1 = GATConv(embed_dim, embed_dim, heads=2, concat=False, edge_dim=embed_dim)
        self.gnn2 = GATConv(embed_dim, embed_dim, heads=2, concat=False, edge_dim=embed_dim)
        
        # Fusion & Prediction
        self.fusion_mlp = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, 1)
        )
        
    def forward(self, data):
        # 1. Text Encoding
        # data.text: [batch_size, seq_len] -> But in PyG batch, text is stacked?
        # Actually data.text is [BatchSize, SeqLen] because we handle it carefully?
        # Wait, in PyG Batch, attributes are concatenated if they are node attributes.
        # But 'text' is a graph-level attribute.
        # PyG Batching logic:
        # If 'text' is not a node attribute, it stacks it if shape matches.
        # data.text is [SeqLen] in Dataset.
        # Batch.text will be [BatchSize * SeqLen] if it flattens, or [BatchSize, SeqLen] if stacked.
        # Let's assume standard stacking [B, L]
        
        # Reshape text
        # data.text is stacked [Batch * SeqLen]
        batch_size = data.num_graphs
        text = data.text.view(batch_size, -1) # [B, L]
        
        text_emb = self.text_embed(text) # [B, L, D]
        # print(f"DEBUG: data.text shape: {data.text.shape}")
        # print(f"DEBUG: text_emb shape: {text_emb.shape}")
        
        _, (h_n, _) = self.lstm(text_emb) # h_n: [1, B, D]
        text_feat = h_n.squeeze(0) # [B, D]
        # print(f"DEBUG: text_feat shape: {text_feat.shape}")
        
        # 2. Node Encoding
        # data.x_cat: [TotalNodes, 2]
        c_emb = self.color_embed(data.x_cat[:, 0]) # [TotalNodes, D/2]
        t_emb = self.type_embed(data.x_cat[:, 1]) # [TotalNodes, D/2]
        p_feat = self.pos_mlp(data.x_cont)        # [TotalNodes, D]
        
        node_feat = torch.cat([c_emb, t_emb], dim=1) + p_feat # [TotalNodes, D]
        
        # 3. Edge Encoding
        edge_feat = self.edge_embed(data.edge_attr) # [TotalEdges, D]
        
        # 4. GNN Layers
        node_feat = F.relu(self.gnn1(node_feat, data.edge_index, edge_attr=edge_feat))
        node_feat = F.relu(self.gnn2(node_feat, data.edge_index, edge_attr=edge_feat))
        
        # 5. Fusion
        # We need to broadcast text_feat to nodes.
        # data.batch is [TotalNodes] -> batch index for each node
        # print(f"DEBUG: data.batch shape: {data.batch.shape}")
        text_feat_expanded = text_feat[data.batch] # [TotalNodes, D]
        # print(f"DEBUG: text_feat_expanded shape: {text_feat_expanded.shape}")
        # print(f"DEBUG: node_feat shape: {node_feat.shape}")
        
        combined = torch.cat([node_feat, text_feat_expanded], dim=1) # [TotalNodes, 2D]
        scores = self.fusion_mlp(combined).squeeze(1) # [TotalNodes]
        
        return scores
