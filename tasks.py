import os
import re
import sys

from invoke import task, Result
from invoke.context import Context
from pathlib import Path

class SomethingWentWrong(Exception): pass

def failsafe(callable):
    "Executes the callable, and if not result.ok raises a RemoteWentWrong exception."
    result: Result = callable()
    if not result.ok:
        raise SomethingWentWrong(result.stderr)


def executes_correctly(c: Context, argument: str) -> bool:
    "returns True if the execution was without error level"
    return c.run(argument, warn=True).ok


def execution_fails(c: Context, argument: str) -> bool:
    "Returns true if the execution fails based on error level"
    return not executes_correctly(c, argument)

def read_dotenv(path:Path):
    with path.open(mode='r') as env_file:
        lines = env_file.read().split('\n')
        # remove comments
        lines = [line.split('#',1)[0] for line in lines]
        # remove redundant whitespace
        lines = [line.strip() for line in lines]
        # keep lines with values
        lines = [line for line in lines if line]
        # convert to tuples
        items = [line.split('=',1) for line in lines]
        # clean the tuples
        items = [(key.strip(), value.strip()) for key,value in items]
        # convert to dict for quick lookup of keys
        return dict(items)


def check_env(path:Path, key:str, default:str):
    """
    Test if key is in .env file path, appends prompted or default value if missing.
    """
    vars = read_dotenv(path)
    if key not in vars:
        with path.open(mode='r+') as env_file:
            response = input(f'Enter value for {key}, default=`{default}`:')
            value = response.strip() or default
            env_file.seek(0,2)
            env_file.write(f'\n{key.upper()}={value}\n')

def apply_dotenv_vars_to_yaml_templates(yaml_path: Path, dotenv_path:Path):
    """Indention preserving templating of yaml files, uses dotenv_path for variables.

    Pythong formatting is used with a dicationary of environment variabes used from environment variables
    updated by the dotenv_path parsed .dotenv entries.
    Templating is found using `# template:`
    indention is saved, everything after the above indicator is python string formatted and written back.

    Example:
        |config:
        |    email: some@one.com # template: {EMAIL}

    assuming dotenv file contains:
        |EMAIL=yep@thatsme.com

    applying this function will result in:
        |config:
        |    email: yep@thatsme.com # template: {EMAIL}
    """
    env = os.environ.copy()
    env.update(read_dotenv(dotenv_path))
    needle = re.compile(r'# *template:')
    env_variable_re = re.compile(r'\$[A-Z0-9]')
    with yaml_path.open(mode='r+') as yaml_file:
        source_lines = yaml_file.read().split('\n')
        new_lines = []
        for line in source_lines:
            if len(needle.findall(line)):
                # split on template definition:
                old, template = needle.split(line)
                template = template.strip()
                # save the indention part, add an addition if no indention was found
                indention = (re.findall(r'^[\s]*',old)+[''])[0]
                if not old.lstrip().startswith('#'):
                    # skip comment only lines
                    new = template.format(**env)
                    # reconstruct the line for the yaml file
                    line = f'{indention}{new} # template: {template}'
            new_lines.append(line)
        # move filepointer to the start of the file
        yaml_file.seek(0,0)
        # write all lines and newlines to the file
        yaml_file.write('\n'.join(new_lines))
        # and remove any part that might be left over (when the new file is shorter than the old one)
        yaml_file.truncate()
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
    check_env(dotenv_path, key='TRAEFIK_CERTIFICATE_EMAIL', default='')
    check_env(dotenv_path, key='TRAEFIK_PILOT_TOKEN', default='default')
    apply_dotenv_vars_to_yaml_templates(Path('traefik.yml'), dotenv_path)
    domain = input('Create a certificate for domain, empty is abort, example "dockers.local": ')
    if domain:
        mk_certificate(c, domain)
    print('Use `invoke up` to start docker container.')

@task
def up(c):
    "docker-compose up -d proxy"
    c:Context = c
    c.run('docker-compose up -d proxy')

@task
def restart(c,follow=False):
    "docker-compose stop and up -d of proxy only"
    c:Context = c
    c.run('docker-compose stop proxy')
    c.run('docker-compose up -d proxy')
    if follow:
        logs(c)
@task
def logs(c, n=100):
    "Tail the proxy log starting with the last n(default=100) lines. "
    c.run(f'docker-compose logs --tail={n} -f proxy')

@task
def pip_for_invoke(c, args=''):
    "BETA: Issue pip commands within the venv of this invoke. "
    print('invoke is run from:',sys.argv[0])
    invoke_path = Path(sys.argv[0])
    pip = invoke_path.parent / 'pip'
    if not pip.exists():
        pip = invoke_path.parent / 'pip3'
    if not pip.exists():
        pip = invoke_path.parent / 'python'
        if pip.exists():
            pip = f'{pip} -m pip '
        else:
            pip = f'{sys.executable} -m pip'
    c.run(f'{pip} {args}')


import pathlib
@task
def mk_certificate(c, domain):
    # heavily inspired by https://stackoverflow.com/questions/19665863/how-do-i-use-a-self-signed-certificate-for-a-https-node-js-server
    try:
        c.run('mkdir server/ client/ root_cert/')
    except:
        pass

    print("create ow own root certificate authority")
    if not pathlib.Path('/root_cert/ca.private.pem').exists():
        c.run("openssl genrsa -out root_cert/ca.private.pem 2048")

    print("self sign the root certificate authority")
    if not pathlib.Path('/root_cert/ca.cert.pem').exists():
        c.run("openssl req -x509 -new -nodes -key root_cert/ca.private.pem -days 10000 -out root_cert/ca.cert.pem "
              " -subj \"/C=NL/O=EDWH Development ONLY/CN=edwh.local\"")

    print("create a new private key for the specific host")
    c.run("openssl genrsa -out server/private.pem 2048")

    print("create a device certificate for a wildcard domain")
    c.run(f'openssl req -new -key server/private.pem -out server/csr.pem -subj "/C=NL/O=EDWH dev/CN=*.{domain}"')

    print("sign the request from device with the root CA")
    c.run("openssl x509 -req -in server/csr.pem "
          "-CA root_cert/ca.cert.pem "
          "-CAkey root_cert/ca.private.pem "
          "-CAcreateserial "
          "-out server/cert.pem "
          "-days 10000")

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