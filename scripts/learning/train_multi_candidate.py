import os
import glob
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch_geometric.data import Data, Batch
from torch_geometric.loader import DataLoader
from torch_geometric.nn import GATConv
from tqdm import tqdm

# =============================================================================
# Dataset
# =============================================================================
class MultiCandidateDataset(torch.utils.data.Dataset):
    def __init__(self, root_dir, split='train', split_ratio=0.8, seed=42):
        self.files = sorted(glob.glob(os.path.join(root_dir, "*.npz")))
        
        # Shuffle files to ensure mixed towns in train/val
        import random
        random.seed(seed)
        random.shuffle(self.files)
        
        # Simple split
        split_idx = int(len(self.files) * split_ratio)
        if split == 'train':
            self.files = self.files[:split_idx]
        else:
            self.files = self.files[split_idx:]
            
        print(f"[{split}] Loaded {len(self.files)} files from {root_dir}")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        try:
            path = self.files[idx]
            data = np.load(path, allow_pickle=True)
            
            node_feats = torch.from_numpy(data['node_feats']).float() # [N, 32]
            edge_index = torch.from_numpy(data['edge_index']).long()  # [2, E]
            edge_attr = torch.from_numpy(data['edge_attr']).float()   # [E, 16]
            lang_feat = torch.from_numpy(data['lang_feat']).float()   # [8]
            target_idx = int(data['target_index'])
            
            # Ensure edge_index is contiguous
            edge_index = edge_index.contiguous()

            return Data(
                x=node_feats,
                edge_index=edge_index,
                edge_attr=edge_attr,
                lang_feat=lang_feat.unsqueeze(0), # [1, 8] for graph-level
                y=torch.tensor([target_idx], dtype=torch.long),
                num_nodes=node_feats.size(0)
            )
        except Exception as e:
            print(f"Error loading {self.files[idx]}: {e}")
            return None

def collate_fn(batch):
    batch = [b for b in batch if b is not None]
    if not batch: return Batch.from_data_list([]) # Return empty batch or handle properly
    return Batch.from_data_list(batch)

# =============================================================================
# Model
# =============================================================================
class SimpleGNN(nn.Module):
    def __init__(self, node_dim=32, edge_dim=16, lang_dim=8, hidden_dim=64):
        super(SimpleGNN, self).__init__()
        
        self.node_enc = nn.Linear(node_dim, hidden_dim)
        self.edge_enc = nn.Linear(edge_dim, hidden_dim)
        self.lang_enc = nn.Linear(lang_dim, hidden_dim)
        
        self.gnn1 = GATConv(hidden_dim, hidden_dim, heads=2, concat=False, edge_dim=hidden_dim)
        self.gnn2 = GATConv(hidden_dim, hidden_dim, heads=2, concat=False, edge_dim=hidden_dim)
        
        self.fusion = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
        
    def forward(self, data):
        # 1. Encode
        x = F.relu(self.node_enc(data.x)) # [TotalNodes, H]
        edge_attr = F.relu(self.edge_enc(data.edge_attr)) # [TotalEdges, H]
        
        # Lang: data.lang_feat is [Batch, 8] -> [Batch, H]
        # data.batch maps node -> batch_idx
        lang_emb = F.relu(self.lang_enc(data.lang_feat)) # [Batch, H]
        
        # 2. GNN
        x = F.relu(self.gnn1(x, data.edge_index, edge_attr=edge_attr))
        x = F.relu(self.gnn2(x, data.edge_index, edge_attr=edge_attr))
        
        # 3. Fusion
        # Expand lang to nodes
        lang_expanded = lang_emb[data.batch] # [TotalNodes, H]
        combined = torch.cat([x, lang_expanded], dim=1)
        scores = self.fusion(combined).squeeze(1) # [TotalNodes]
        
        return scores

# =============================================================================
# Train Loop
# =============================================================================
def train():
    ROOT = "data/multi_candidate_data"
    BATCH_SIZE = 32
    EPOCHS = 10 # Increased for harder dataset
    LR = 1e-3
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {DEVICE}")

    train_ds = MultiCandidateDataset(ROOT, split='train')
    val_ds = MultiCandidateDataset(ROOT, split='val')
    
    if len(train_ds) == 0:
        print("No data found! Please run collection first.")
        return

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_fn)
    
    model = SimpleGNN().to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=LR)
    
    # Loss: LogSoftmax + NLL (Ranking Loss)
    # We want to maximize score of target node among all nodes in the graph
    
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        correct = 0
        total_graphs = 0
        
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}")
        for batch in pbar:
            if batch is None or batch.num_graphs == 0: continue
            batch = batch.to(DEVICE)
            optimizer.zero_grad()
            
            scores = model(batch)
            
            # Compute loss per graph using LogSoftmax
            # We use torch_geometric.utils.softmax to compute softmax per graph
            from torch_geometric.utils import softmax
            log_probs = torch.log(softmax(scores, batch.batch) + 1e-10)
            
            # batch.ptr gives start indices
            # global target indices = start_indices + batch.y
            start_indices = batch.ptr[:-1]
            global_targets = start_indices + batch.y
            
            loss = -log_probs[global_targets].mean()
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
            # Acc
            with torch.no_grad():
                for i in range(len(batch.ptr)-1):
                    start = batch.ptr[i]
                    end = batch.ptr[i+1]
                    graph_scores = scores[start:end]
                    if graph_scores.argmax() == batch.y[i]:
                        correct += 1
            total_graphs += (len(batch.ptr)-1)
            
            pbar.set_postfix({'loss': total_loss/(pbar.n+1), 'acc': correct/total_graphs})
            
        # Val
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for batch in val_loader:
                if batch is None: continue
                batch = batch.to(DEVICE)
                scores = model(batch)
                for i in range(len(batch.ptr)-1):
                    start = batch.ptr[i]
                    end = batch.ptr[i+1]
                    if scores[start:end].argmax() == batch.y[i]:
                        val_correct += 1
                val_total += (len(batch.ptr)-1)
        
        val_acc = val_correct / val_total if val_total > 0 else 0
        print(f"Val Acc: {val_acc:.4f}")

if __name__ == "__main__":
    train()
