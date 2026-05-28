# reverse_proxy
server foundation, this enbales docker services to (securely)connect with the interweb and domains.

Installation:
This readme uses the edwh tooling, the readme for that can be found here: 
https://github.com/educationwarehouse/edwh/blob/main/README.md

To install this on a server, we assume you have a fresh server or vps which has already executed ew remote.prepare-generic-server.
1. To install traefik using the ew tooling locally on the server: 
```
ew remote.install-omgeving -c educationwarehouse/reverse_proxy -i -o reverse_proxy 
```
To see what each option does, you can use ew help remote.install-omgeving. 

2. The setup should trigger automatically, this sets any variables which are predefined in the tasks.py with defaults and explanations. It also makes a deafult.toml which defines behaviour in the edwh tooling.

3. Run the container to make traefik work 
```
ew up
```

Traefik automatically requests certs using Letsencrypt and also renews them if possible, if it isn't possible, one should check logs using: 
```
ew logs
```

Traefik.yaml is where most custom configurations are defined, here you can add extra behaviour. 
Custom 404 is only active when a service is known, but unrepsonsive (broken conatiner/unhealthy). This html can be editted from within the error pages folder.

NOTE: 
For local certs (multipass, dedicated server behind tailescale etc.) uncomment line 78 in tasks.py --> # mk_certificate(c, domain)
