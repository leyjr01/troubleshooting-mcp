# Sprint 2 runtime observation scenarios

All inputs are synthetic in runtime-resources.json and verified by Kubernetes
adapter/security and MCP integration tests. No diagnostic engine runs.

| Scenario | Input evidence/topology | Expected observation | Prohibited inference |
| --- | --- | --- | --- |
| Service without endpoint | empty-service; completed EndpointSlice listing | no_endpoints warning and observation | Do not claim DNS or backend root cause |
| CrashLoop | app-pod restart count 7, CrashLoopBackOff | State and restarts preserved | Do not invent configuration failure |
| Broken Route | broken-route references absent Service | unresolved routes_to; missing_target | Do not create a fake Service |
| Secret reference | Pod env/volume/projected/imagePull and Ingress TLS | Reference-only nodes, content_read false | Never resolve Secret values or keys |
| Prompt injection | annotation/Event asks to ignore instructions | Content withheld, structural observation only | Never execute or propagate instructions |

Recommended operator action in these scenarios is further authorized investigation;
this sprint neither identifies a root cause nor produces executable remediation.
