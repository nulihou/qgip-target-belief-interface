import os
import json
import torch
import numpy as np
from torch.utils.data import Dataset
from torch_geometric.data import Data
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from scripts.modules.perception_oracle import PerceptionOracle
from scripts.modules.logic_adapter import LogicAdapter

class VLNDataset(Dataset):
    def __init__(self, data_root, split='train', max_len=20):
        self.data_root = data_root
        self.split = split
        self.max_len = max_len
        
        # Load split
        split_path = os.path.join(data_root, "splits", f"{split}.txt")
        with open(split_path, 'r') as f:
            self.seq_names = [line.strip() for line in f.readlines()]
            
        self.sequences_dir = os.path.join(data_root, "sequences")
        
        # Initialize modules
        self.logic_adapter = LogicAdapter()
        
        # Vocab
        self.vocab = {
            "<pad>": 0, "<unk>": 1, "follow": 2, "the": 3, ".": 4,
            "red": 5, "green": 6, "blue": 7, "white": 8, "black": 9, 
            "grey": 10, "silver": 11, "yellow": 12, "orange": 13, 
            "brown": 14, "purple": 15, "dark": 16,
            "police": 17, "car": 18, "ambulance": 19, "firetruck": 20, 
            "van": 21, "truck": 22, "motorcycle": 23, "cyclist": 24, 
            "jeep": 25, "vehicle": 26,
            "on": 27, "your": 28, "left": 29, "right": 30, "front": 31, 
            "ahead": 32, "behind": 33, "center": 34
        }
        
        self.color_map = {
            'unknown': 0, 'red': 1, 'green': 2, 'blue': 3, 'white': 4, 
            'black': 5, 'grey': 6, 'silver': 7, 'yellow': 8, 'orange': 9, 
            'brown': 10, 'purple': 11, 'dark blue': 12, 'dark green': 13
        }
        
        self.type_map = {
            'object': 0, 'car': 1, 'van': 2, 'truck': 3, 'motorcycle': 4, 
            'cyclist': 5, 'jeep': 6, 'police car': 7, 'ambulance': 8, 
            'firetruck': 9
        }
        
        self.rel_map = {
            'left': 0, 'right': 1, 'front': 2, 'behind': 3
        }

    def __len__(self):
        return len(self.seq_names)

    def text_to_indices(self, text):
        tokens = text.lower().replace('.', ' .').replace(',', ' ').split()
        indices = [self.vocab.get(t, self.vocab["<unk>"]) for t in tokens]
        if len(indices) < self.max_len:
            indices += [self.vocab["<pad>"]] * (self.max_len - len(indices))
        else:
            indices = indices[:self.max_len]
        return torch.tensor(indices, dtype=torch.long)

    def __getitem__(self, idx):
        seq_name = self.seq_names[idx]
        seq_dir = os.path.join(self.sequences_dir, seq_name)
        
        # Oracle needs to be re-inited per sequence (cheap) or cached?
        # Re-init is safer to avoid state leak, but slightly slower.
        # Given 2000 seqs, it's fine.
        try:
            oracle = PerceptionOracle(seq_dir)
        except Exception as e:
            # print(f"Error loading {seq_name}: {e}")
            return None
        
        # Load instructions
        instr_path = os.path.join(seq_dir, "instructions.json")
        if not os.path.exists(instr_path):
            return None
            
        with open(instr_path, 'r') as f:
            instructions = json.load(f)
            
        if not instructions:
            return None
            
        # Pick random frame
        num_frames = len(oracle.trace['frame_ids'])
        # Try to find a valid frame where target is visible
        for _ in range(10): # Try 10 times
            frame_idx = np.random.randint(0, num_frames)
            
            detections = oracle.get_detections(frame_idx)
            if not detections:
                continue
                
            nodes, edges = self.logic_adapter.build_graph(detections, oracle.width, oracle.height)
            
            # Find target node
            try:
                target_id = int(oracle.trace['target_id'])
            except:
                continue
                
            target_node_idx = -1
            for i, node in enumerate(nodes):
                if node['id'] == target_id:
                    target_node_idx = i
                    break
            
            if target_node_idx != -1:
                # Found valid frame
                break
        else:
            # Failed to find valid frame
            return None

        # Prepare Graph Data
        # Node Features: [Color(Embed), Type(Embed), PosX, PosY, Depth]
        # We will handle Embeddings in the model. Here we pass indices.
        # x_cat: [NumNodes, 2] (ColorIdx, TypeIdx)
        # x_cont: [NumNodes, 3] (Center3D_Norm)
        
        x_cat = []
        x_cont = []
        
        for node in nodes:
            c_idx = self.color_map.get(node['color'], 0)
            t_idx = self.type_map.get(node['label'], 0)
            
            # Normalize pos? 
            # Center 3D is in meters. 
            # x ~ [-10, 10], z ~ [0, 50]
            p = node['center_3d']
            x_cont.append([p[0]/10.0, p[1]/2.0, p[2]/50.0]) # Simple normalization
            x_cat.append([c_idx, t_idx])
            
        x_cat = torch.tensor(x_cat, dtype=torch.long)
        x_cont = torch.tensor(x_cont, dtype=torch.float)
        
        # Edges
        edge_index = []
        edge_attr = []
        
        for u, v, rel in edges:
            edge_index.append([u, v])
            edge_attr.append(self.rel_map.get(rel, 0))
            
        if not edge_index:
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_attr = torch.empty((0), dtype=torch.long)
        else:
            edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
            edge_attr = torch.tensor(edge_attr, dtype=torch.long)
            
        # Instruction
        instr_text = np.random.choice(instructions)
        text_tensor = self.text_to_indices(instr_text)
        
        # Construct Data object
        data = Data(
            x_cat=x_cat,
            x_cont=x_cont,
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=torch.tensor([target_node_idx], dtype=torch.long),
            text=text_tensor,
            num_nodes=len(nodes)
        )
        
        return data

def collate_fn(batch):
    # Filter Nones
    batch = [b for b in batch if b is not None]
    if not batch:
        return None
    from torch_geometric.data import Batch
    try:
        return Batch.from_data_list(batch)
    except Exception as e:
        print(f"Error in collate_fn: {e}")
        # Check if any element is None
        for i, b in enumerate(batch):
            if b is None:
                print(f"Element {i} is None!")
            else:
                pass # print(f"Element {i} type: {type(b)}")
        raise e
