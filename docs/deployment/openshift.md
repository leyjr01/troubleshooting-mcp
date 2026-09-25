# OpenShift deployment

Use the [Kubernetes base](kubernetes.md). The image defaults to non-root UID 10001,
group 0, but all application files are readable and writable data goes only to
the mounted `/tmp`. Deployment imposes no runAsUser or fixed fsGroup; allow the
restricted SCC to assign them. No anyuid/privileged SCC is required by the design.
Actual SCC admission and image execution remain NOT EXECUTED in this environment.

Optionally apply `deploy/openshift/reader.yaml` in each authorized namespace for
get/list on `route.openshift.io/routes` and `apps.3scale.net/apimanagers`. Configure
`provider: openshift`, the APIManager allowlist and 3scale gateway from
`config/server/threescale.example.yaml`, preserving the in-cluster authentication
binding, namespace restrictions and HTTP bearer settings of the base profile.
Do not simply overlay the local kubeconfig example without adjusting those fields.

`deploy/openshift/route.yaml` is optional. Replace its placeholder host and add the
same exact hostname to server.allowed_hosts. Edge TLS redirects insecure clients;
the router forwards to the Service over HTTP. Use cluster-managed certificates,
never repository certificate/key files. Configure router access-log redaction and
appropriate timeouts for bounded MCP requests. Client authorization headers must
reach the server; forwarded principal headers are not trusted.

On vanilla Kubernetes omit the Route and optional API Role. Missing OpenShift
APIs produce bounded unavailable/partial discovery, not a platform lock-in.
No 3scale installation or OpenShift Local provisioning is performed. Real Route,
APIManager and 3scale qualification requires the opt-in
[real-lab profile](../development/real-lab.md).
