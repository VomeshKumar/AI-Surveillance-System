# Windows Node Setup Guide

## Prerequisites
- HP Victus or similar Windows Edge Node
- Python 3.11+
- Git

## Provisioning
1. Open PowerShell as Administrator.
2. Run `.\scripts\deploy_node.ps1 -NodeId "node_00X"`.
3. Ensure `.onnx` models are placed in the `artifacts/` folder.
4. Verify services are running in Windows `services.msc`.
