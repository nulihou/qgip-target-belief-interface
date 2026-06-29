# Final Dataset Split Check

This check inspects `data/final_dataset/{train,val,test_unseen}.json` for path counts, town composition, missing files, and split overlap.

## Split Summary

| Split | n | Existing files | Missing files | Town counts | Difficulty counts |
|---|---:|---:|---:|---|---|
| train | 4050 | 4050 | 0 | Town03:2227; Town04:900; Town10HD:923 | Ultra:4050 |
| val | 450 | 450 | 0 | Town03:273; Town04:100; Town10HD:77 | Ultra:450 |
| test_unseen | 500 | 500 | 0 | Town05:500 | Ultra:500 |

## Overlap

| Pair | Overlap paths |
|---|---:|
| train vs val | 0 |
| train vs test_unseen | 0 |
| val vs test_unseen | 0 |
