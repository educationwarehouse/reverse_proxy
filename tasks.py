import contextlib
import os
import re
import sys

from invoke import task, Result
from invoke.context import Context
from pathlib import Path
import edwh

@task
def setup(c):
    "Setup or update the traefik environment."
    print('Setting up reverse proxy...')
    if not Path('./logs').exists():
        c.run('mkdir ./logs')
    if not Path('./letsencrypt').exists():
        c.run('mkdir ./letsencrypt')
    # force access rights
    c.sudo('chmod 770 ./letsencrypt')
    if list(Path('./letsencrypt').glob('*')):
        c.sudo('chmod 600 ./letsencrypt/*')
    dotenv_path = Path('.env')
    if not dotenv_path.exists():
        dotenv_path.touch()
    # check these options
    edwh.tasks.check_env(key='TRAEFIK_CERTIFICATE_EMAIL', default='', comment='Required email for letsencrypt')
    edwh.tasks.check_env(key='TRAEFIK_PILOT_TOKEN', default='default', comment='Optional pilot token for traefik')
    domain = edwh.tasks.check_env(key='HOSTINGDOMAIN', default='dockers.local', comment='From which domain will you access your dockers? (used to host web2py subdomain for CAS and domain certificates)')
    mk_certificate(c, domain)
    edwh.tasks.apply_dotenv_vars_to_yaml_templates(Path('traefik.yml'), dotenv_path)
    print(f'Use `{Path(sys.argv[0]).name} up` to start docker container.')


@task
def mk_certificate(c, domain):
    # heavily inspired by https://stackoverflow.com/questions/19665863/how-do-i-use-a-self-signed-certificate-for-a-https-node-js-server
    print('Making certificates for domain', domain)
    from invoke import Runner
    c: Runner
    c.run('mkdir server/ client/ root_cert/', hide=True, warn=True, echo=False)

    print("create ow own root certificate authority")
    if not Path('root_cert/ca.private.pem').exists():
        c.run("openssl genrsa -out root_cert/ca.private.pem 2048")
    else:
        print('already exists.')

    print("self sign the root certificate authority")
    if not Path('root_cert/ca.cert.pem').exists():
        c.run("openssl req -x509 -new -nodes -key root_cert/ca.private.pem -days 10000 -out root_cert/ca.cert.pem "
              " -subj \"/C=NL/O=EDWH Development ONLY/CN=edwh.local\"")
    else:
        print('already exists.')

    print("create a new private key for the specific host")
    if not Path('server/private.pem').exists():
        c.run("openssl genrsa -out server/private.pem 2048")
    else:
        print('already exists')

    print("create a device certificate for a wildcard domain")
    if not Path('server/csr.pem').exists():
        c.run(f'openssl req -new -key server/private.pem -out server/csr.pem -subj "/C=NL/O=EDWH dev/CN=*.{domain}"')
    else:
        print('already exists')

    print("sign the request from device with the root CA")
    if not Path('server/cert.pem').exists():
        c.run("openssl x509 -req -in server/csr.pem "
              "-CA root_cert/ca.cert.pem "
              "-CAkey root_cert/ca.private.pem "
              "-CAcreateserial "
              "-out server/cert.pem "
              "-days 10000")
    else:
        print('already exists')

    print("create a fullchain, because mostly you need a fullchain")
    c.run("cp root_cert/ca.cert.pem server/fullchain.pem")

    print("cp the root ca's pem file for the client to use (if you want to)")
    c.run("cp root_cert/ca.cert.pem client/ca.cert.pem")

    print("perpare a DER format crt for IOS etc")
    c.run("openssl x509 -outform der -in root_cert/ca.cert.pem -out client/ca.cert.der-format.crt")

    with open('server/dynamic.yaml','w')  as stream:
        import textwrap
        stream.write(textwrap.dedent('''
        tls:
          stores:
            default:
              defaultCertificate:
                certFile: /server/cert.pem
                keyFile: /server/private.pem
        '''))