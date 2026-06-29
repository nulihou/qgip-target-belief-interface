import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import os
import sys
from tqdm import tqdm

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from scripts.learning.dataset import VLNDataset, collate_fn
from scripts.learning.model import BaselineGNN

def train():
    # Config
    DATA_ROOT = "data/seq_2k"
    BATCH_SIZE = 32
    LR = 1e-3
    EPOCHS = 10
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    print(f"Using device: {DEVICE}")
    
    # Dataset
    train_dataset = VLNDataset(DATA_ROOT, split='train')
    val_dataset = VLNDataset(DATA_ROOT, split='val')
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_fn)
    
    # Model
    # Vocab sizes from dataset
    # Note: Hardcoded in dataset, so we match them here
    model = BaselineGNN(
        vocab_size=35, # len(train_dataset.vocab) approx
        color_num=14,  # len(train_dataset.color_map)
        type_num=10,   # len(train_dataset.type_map)
        rel_num=4      # len(train_dataset.rel_map)
    ).to(DEVICE)
    
    optimizer = optim.Adam(model.parameters(), lr=LR)
    criterion = nn.CrossEntropyLoss()
    
    # Checkpoints
    os.makedirs("checkpoints", exist_ok=True)
    
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS}")
        for batch in pbar:
            if batch is None: continue
            
            batch = batch.to(DEVICE)
            optimizer.zero_grad()
            
            # Forward
            scores = model(batch) # [TotalNodes]
            
            # Loss Calculation
            # We need to compute loss per graph.
            # batch.y contains index of target node IN THE GRAPH
            # But scores is flat [TotalNodes].
            # We need to mask scores per graph and use Softmax/CrossEntropy.
            
            # Trick: Use torch_geometric.utils.softmax? 
            # Or simpler: Split scores by batch.batch
            
            # Efficient implementation:
            # Since we only have 1 positive per graph, we can just use CrossEntropy
            # But standard CrossEntropy expects [Batch, NumClasses].
            # Here graphs have variable node counts.
            
            # Approach:
            # 1. Get true global indices of targets
            # batch.y is local index (0..NumNodesInGraph-1)
            # We need global index in the flattened batch.
            # batch.ptr tells us start index of each graph.
            
            # batch.ptr: [0, N1, N1+N2, ...]
            start_indices = batch.ptr[:-1]
            global_targets = start_indices + batch.y
            
            # But wait, CrossEntropy needs logits for ALL classes.
            # Here "classes" are nodes in the graph.
            # This is "Learning to Rank" or "Pointer Network" style.
            
            # Easier way: LogSoftmax per graph, then select log-prob of target.
            from torch_geometric.utils import softmax
            log_probs = torch.log(softmax(scores, batch.batch) + 1e-10)
            
            loss = -log_probs[global_targets].mean()
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
            # Accuracy
            # Argmax per graph
            
            # Manual loop for accuracy (slow but safe for verification)
            batch_correct = 0
            for i in range(len(batch.ptr) - 1):
                start = batch.ptr[i]
                end = batch.ptr[i+1]
                graph_scores = scores[start:end]
                pred = graph_scores.argmax()
                if pred == batch.y[i]:
                    batch_correct += 1
                    
            correct += batch_correct
            total += (len(batch.ptr) - 1)
            
            pbar.set_postfix({'loss': total_loss / (pbar.n + 1), 'acc': correct / total})
            
        # Validation
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for batch in val_loader:
                if batch is None: continue
                batch = batch.to(DEVICE)
                scores = model(batch)
                
                for i in range(len(batch.ptr) - 1):
                    start = batch.ptr[i]
                    end = batch.ptr[i+1]
                    graph_scores = scores[start:end]
                    pred = graph_scores.argmax()
                    if pred == batch.y[i]:
                        val_correct += 1
                val_total += (len(batch.ptr) - 1)
                
        val_acc = val_correct / val_total if val_total > 0 else 0
        print(f"Epoch {epoch+1} Val Acc: {val_acc:.4f}")
        
        # Save
        torch.save(model.state_dict(), f"checkpoints/baseline_epoch_{epoch+1}.pth")

if __name__ == "__main__":
    train()
