import sys
import os

print("Initializing V7 Training Script...")

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset
    import numpy as np
    import glob
    from torch_geometric.nn import GATv2Conv
    from torch_geometric.data import Data, Batch
    from torch_geometric.loader import DataLoader as PyGDataLoader
    print("✅ All imports successful.")
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

# ==============================================================================
# 1. Dataset
# ==============================================================================
class LeaderDataset(Dataset):
    def __init__(self, data_dir):
        self.files = glob.glob(os.path.join(data_dir, "*.npz"))
        print(f"Found {len(self.files)} samples in {data_dir}")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        try:
            path = self.files[idx]
            data = np.load(path)
            
            x = torch.from_numpy(data['x']).float()
            edge_index = torch.from_numpy(data['edge_index']).long()
            edge_attr = torch.from_numpy(data['edge_attr']).float()
            y = torch.tensor(data['y']).long() 
            
            return Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y)
        except Exception as e:
            print(f"Error loading {path}: {e}")
            # Return a dummy data to avoid crashing
            return Data(x=torch.zeros(2,32), edge_index=torch.zeros(2,0).long(), edge_attr=torch.zeros(0,16), y=torch.tensor(0))

# ==============================================================================
# 2. Model
# ==============================================================================
class LeaderClassifier(nn.Module):
    def __init__(self, node_dim=32, edge_dim=16, hidden_dim=64):
        super().__init__()
        self.node_enc = nn.Sequential(nn.Linear(node_dim, hidden_dim), nn.ReLU())
        self.edge_enc = nn.Sequential(nn.Linear(edge_dim, hidden_dim), nn.ReLU())
        
        self.conv1 = GATv2Conv(hidden_dim, hidden_dim, edge_dim=hidden_dim, add_self_loops=False)
        self.conv2 = GATv2Conv(hidden_dim, hidden_dim, edge_dim=hidden_dim, add_self_loops=False)
        
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, x, edge_index, edge_attr, batch=None):
        x = self.node_enc(x)
        edge_attr = self.edge_enc(edge_attr)
        x = x + self.conv1(x, edge_index, edge_attr)
        x = torch.relu(x)
        x = x + self.conv2(x, edge_index, edge_attr)
        x = torch.relu(x)
        scores = self.head(x).squeeze(-1)
        return scores

# ==============================================================================
# 3. Training Loop
# ==============================================================================
def train(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    dataset = LeaderDataset(args.data_dir)
    if len(dataset) == 0:
        print("No data found!")
        return

    loader = PyGDataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    
    model = LeaderClassifier().to(device)
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()
    
    print("Start Training...")
    model.train()
    
    for epoch in range(args.epochs):
        total_loss = 0
        correct = 0
        total_graphs = 0
        
        for batch in loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            
            scores = model(batch.x, batch.edge_index, batch.edge_attr)
            
            loss = 0
            ptr = batch.ptr
            
            for i in range(len(ptr) - 1):
                start, end = ptr[i], ptr[i+1]
                graph_scores = scores[start:end]
                target_idx = batch.y[i]
                
                if target_idx >= (end - start): continue
                
                loss += criterion(graph_scores.unsqueeze(0), target_idx.unsqueeze(0))
                
                if graph_scores.argmax() == target_idx:
                    correct += 1
                total_graphs += 1
            
            if total_graphs > 0:
                loss = loss / (len(ptr) - 1)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
        avg_loss = total_loss / len(loader)
        acc = correct / max(1, total_graphs)
        print(f"Epoch {epoch+1}/{args.epochs} | Loss: {avg_loss:.4f} | Acc: {acc:.2%}")
        
        if (epoch+1) % 10 == 0:
            os.makedirs(args.save_dir, exist_ok=True)
            torch.save(model.state_dict(), os.path.join(args.save_dir, f"llc_epoch_{epoch+1}.pth"))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default="data/v7_leader_data")
    parser.add_argument("--save_dir", default="checkpoints/v7")
    parser.add_argument("--epochs", type=int, default=20) # 默认 20 epoch
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()
    
    train(args)
