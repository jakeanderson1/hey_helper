import sys, os
import subprocess
import functools
import getpass
from io import open
from yaml import load
from yaml import Loader
from time import sleep

COMMANDS = {}

NONINTERACTIVE = {}

CONFIG = {
    'default_container': 'django',
    'compose_files': ['docker-compose.DEV.yml']
}

def command(_func=None, *, command_name=None, noninteractive=False):
    def decorator_command_noargs(func):
        command_name = func.__name__
        if noninteractive:
            NONINTERACTIVE[command_name] = func
        else:
            COMMANDS[command_name] = func
        return func

    def decorator_command(func, command_name, noninteractive):
        if not command_name:
            command_name = func.__name__
        if noninteractive:
            NONINTERACTIVE[command_name] = func
        else:
            COMMANDS[command_name] = func

        @functools.wraps(func)
        def wrapper_command(*args, **kwargs):
            value = func(*args, **kwargs)
            return value
        return wrapper_command
    
    if _func is None:
        return decorator_command_noargs
    else:
        return decorator_command(_func, command_name, noninteractive)


def _handle_err(cmd):
    if cmd.returncode != 0:
        msg = getattr(cmd, 'stderr', b'No error message')
        if msg:
            print("There was a problem:", msg.decode())
        sys.exit(1)
    return cmd

def _get_config_file_here(filepath):
    valid_filenames = ['hey.yml', 'hey.yaml']
    filename = next((f for f in os.listdir(filepath) if f in valid_filenames), None)
    return filename

def _go_to_working_dir():
    this_dir = os.path.dirname(os.path.realpath(__file__))
    current_dir = os.path.realpath(os.curdir)
    config_root = _get_config_file_here(current_dir)
    while not config_root:
        previous_dir = current_dir
        current_dir = os.path.join(current_dir, os.path.pardir)
        if os.path.realpath(previous_dir) == os.path.realpath(current_dir):
            # Shockingly there isn't a better way to figure out if we're at root?
            break
        config_root = _get_config_file_here(current_dir)
    if config_root:
        os.chdir(current_dir)
        print("wk_dir(config root): ", current_dir)

        with open(os.path.join(current_dir, config_root), 'r') as stream:
            loaded_config = load(stream, Loader=Loader)
            if loaded_config:
                CONFIG.update(loaded_config)
            # print(CONFIG)
        return current_dir

    wk_dir = os.path.join(this_dir, os.path.pardir)
    os.chdir(wk_dir)
    print("wk_dir: ", wk_dir)
    return wk_dir

_go_to_working_dir()

def _docker_compose(command_array, compose_files=None, handle_errors=True):
    if not compose_files:
        compose_files = CONFIG.get('compose_files', ['docker-compose.DEV.yml'])
        if type(compose_files) is not list:
            if ';' in compose_files:
                compose_files = compose_files.split(';')
            else:
                compose_files = [compose_files]

    command = ['docker-compose']
    for cf in compose_files:
        if os.path.isfile(cf):
            command += ['-f', cf]
    command += command_array

    print('Command: ', '`', ' '.join(command).strip(), '`', sep='')
    if handle_errors:
        return _handle_err(subprocess.run(command, stderr=subprocess.PIPE))
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _command_match(cmd):
    if cmd.isdigit() and int(cmd) < len(COMMANDS.keys()):
        COMMANDS[list(COMMANDS.keys())[int(cmd)]]()
        return True

    matches = [c for c in all_commands.keys() if c.lower() == cmd.lower()]
    if len(matches) == 1:
        all_commands[matches[0]]()
        return True
    elif len(matches) > 1:
        print('Shortcut "{}" matches multiple commands:'.format(cmd))
        for m in matches: print(" -", m)
    else:
        print("Command not found.")

def _run_command(command_array, *args, **kwargs):
    print('Command: ', '`', ' '.join(command_array).strip(), '`', sep='')
    cmd = subprocess.run(command_array, stderr=subprocess.PIPE, shell=True, *args, **kwargs)
    return _handle_err(cmd)

@command
def bash():
    '''Get a bash prompt inside the default container'''
    print('Getting you into bash inside the {} container...'.format(CONFIG.get('default_container', 'django')))
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash'])


@command
def shell():
    '''Open a python shell inside the default container'''
    print('Opening a python shell inside the {} container...'.format(CONFIG.get('default_container', 'django')))
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c', 'python /code/django/manage.py shell'])


@command
def test():
    '''Run the unit test suite with pytest'''
    print('Running tests...')
    args = ''
    if len(sys.argv) > 2:
        args = ' '.join(sys.argv[2:])
    print(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c', 'cd /code/django; pytest {}'.format(args)])
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c',
                                  'cd /code/django; pytest {}'.format(args)])

@command
def mail():
    '''Run a local SMTP debug server that prints outgoing email'''
    print("Listening for mail at localhost:2525...")
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c',
                     'python -m smtpd -n -c DebuggingServer localhost:2525'])

@command
def logs():
    '''Most recent container log lines (default: last 10 of django)'''
    print('Showing logs. HINT: you can add `--tail <num>` and/or a container name...')
    args = ['--tail', '10', CONFIG.get('default_container', 'django')]
    if len(sys.argv) > 2:
        args = sys.argv[2:]
    _docker_compose(['logs'] + args)

@command(noninteractive=True)
def dc():
    '''Run docker-compose commands with the config file pre-set'''
    if len(sys.argv) > 2:
        _docker_compose(sys.argv[2:])

def sstop():
    '''Stop all supervisor jobs'''
    print('Stopping supervisor...')
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c', 'supervisorctl -u admin -p @rg0n18 stop all'])

def sstart():
    '''Start all supervisor jobs'''
    print('Starting supervisor...')
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c', 'supervisorctl -u admin -p @rg0n18 start all'])

@command
def up():
    '''\t Start (or recreate) the containers'''
    print('Re-creating the containers...')
    args = []
    if len(sys.argv) > 2:
        args = sys.argv[2:]
    _docker_compose(['up'] + args)

@command
def stop():
    '''Stops the containers'''
    print('Stopping the containers...')
    _docker_compose(['stop'])


@command
def down():
    '''Destroy the containers & network'''
    print('Taking the containers down...')
    _docker_compose(['down'])

def get_scp_command():
    scp = 'scp'
    if os.name == 'nt':
        scp = 'C:/Program Files/Git/usr/bin/scp'
    return scp

@command
def getbackup():
    '''Download the latest prod database backup'''
    print('Checking for latest backup...')
    # dirpath = _go_to_working_dir()
    dirpath = "../"
    ssh = 'ssh'
    if os.name == 'nt':
        ssh = 'C:/Program Files/Git/usr/bin/ssh'
    cmd = subprocess.run([ssh, 'jakea@atc-de01.aluminumtrailer.local', 'ls -1r /home/dev.bot/Public | head -1'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _handle_err(cmd)

    latest = cmd.stdout.strip().decode()
    print('Downloading {} to the folder {}...'.format(latest, dirpath))
    _handle_err(subprocess.run([get_scp_command(), 'jakea@atc-de01.aluminumtrailer.local:/home/dev.bot/Public/{}'.format(latest), dirpath],
                      stderr=subprocess.PIPE))
    print('Download complete! Your backup file is in the folder, ready to restore.')
    return latest

@command
def restore():
    '''Restore the database from a tarfile in the work folder'''
    dump = None
    if not len(sys.argv) > 2:
        dl = input("No file specified, would you like to download the latest prod backup? Y/n: ")
        if dl.lower() == 'n':
            return
        else:
            dump = getbackup()

    print('Restoring database...')
    _docker_compose(['stop'])

    this_dir = os.path.dirname(os.path.realpath(__file__))
    # wk_dir = os.path.join(this_dir, os.path.pardir)
    wk_dir = _go_to_working_dir()
    if not dump:
        dump = os.path.basename(sys.argv[2])

    print("Restoring data in container to wk_dir {}...".format(wk_dir))
    _handle_err(_run_command(['docker', 'run', '--mount',
        'type=bind,src={},destination=/pg_restore_src'.format(wk_dir), '--mount',
        'type=volume,src=data,destination=/pg_restore_dest', 'ubuntu', 'bash', '-c',
            "cd /pg_restore_dest; \
            echo '    Removing old data'; rm -R /pg_restore_dest/*; \
            echo '    Extracting backup data'; tar xf /pg_restore_src/{}".format(dump)]))

    print('Stopping postgres...')
    _docker_compose(['up', '-d', 'postgres'])

    print('Cleaning up...')
    r = None
    while '(1 row)' not in str(getattr(r, 'stdout', '')):
        r = _docker_compose(['exec', 'postgres', 'bash', '-c',
                             "psql -d argon -U argondb -c 'select 1'"], handle_errors=False)
        sleep(1)

    _docker_compose(['exec', '-d', 'postgres', 'bash', '-c', '''
        psql -U argondb -d argon -c \"
        UPDATE argon_users_user SET email='donotreply-{0}@aluminumtrailer.com' WHERE username='admin';
        UPDATE argon_users_user SET email='{0}@aluminumtrailer.com' WHERE username='{0}';
        UPDATE argon_users_user SET email='' WHERE username='trishz';

        DELETE FROM argon_users_user_groups ug WHERE group_id=5;

        INSERT INTO argon_users_user_groups (user_id, group_id)
        SELECT u.id, 5
        FROM argon_users_user u
        WHERE username='{0}';

        UPDATE argon_devices_device SET active=FALSE WHERE is_healthy=FALSE; \"'''.format(getpass.getuser())])

    print('\nYour database has been restored!\n',
          'You can now re-start your containers. Remember to run migrations!', sep='')


@command
def mkmigrations():
    '''Generate database migrations for schema changes'''
    print('Making migrations...')
    args = ''
    if len(sys.argv) > 2:
        args = ' '.join(sys.argv[2:])
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c',
                     'python /code/django/manage.py makemigrations {}'.format(args)])


@command
def migrate():
    '''Apply migrations to the database'''
    print('Migrating...')
    args = ''
    if len(sys.argv) > 2:
        args = ' '.join(sys.argv[2:])
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c',
                     'python /code/django/manage.py migrate {}'.format(args)])

@command
def jsbuild():
    '''Run a webpack build'''
    args = ''
    if len(sys.argv) > 2:
        args = ' '.join(sys.argv[2:])
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c',
                     'cd /code/django/js; npm run build {}'.format(args)])

@command
def jsserve():
    '''Run the webpack dev server'''
    _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c', 'cd /code/django/js; npm run serve'])

@command
def npm():
    '''Run arbitrary npm commands in the container'''
    if len(sys.argv) > 2:
        _docker_compose(['exec', CONFIG.get('default_container', 'django'), 'bash', '-c',
                         'cd /code/django/js; npm {}'.format(' '.join(sys.argv[2:]))])

def collectstatic():
    '''Copy all static assets to argon/static'''
    _manage_py('collectstatic --no-input')

@command
def alias():
    '''Learn how to set up an alias for this script'''
    print(r'''Alias setup

On Windows, find your profile location with `$profile`. Create and add this to the contents of that file:
    function hey {
         python C:\path\to\scripts\hey_helpers.py @args
    }

On linux/macOS add this to your bash profile:
    alias hey="python /path/to/scripts/hey_helpers.py"
''')

@command
def pubkey():
    '''Learn how to get backup files without password prompts'''
    print('''
Passwordless login with publickey authentication
Note: you may have to create the files named here if they don't exist

1. Run `ssh-keygen` (the default arguments work fine)
2. Copy the contents of ~/.ssh/id_rsa.pub (default name and location)
3. Connect to atc-de01, and paste those contents into the ~/.ssh/authorized_keys file
4. Test your connection with `ssh -i ~./ssh/id_rsa atc-de01`
5. If successful, add these contents to the ~/.ssh/config file on *your computer*:
    Host atc-de01
        User <your remote username>
        IdentityFile ~/.ssh/id_rsa.pub
6. Test your config by trying `ssh atc-de01`. It should log you in with no prompt!

Now you should be able to run `hey getbackup` and have it work automagically
''')

@command(command_name='get-credentials')
def getcredentials():
    '''Get google cloud kubernetes credentials'''
    command = ['gcloud', 'container', 'clusters', 'get-credentials', '--zone', 'us-central1-f', '--project', 'habitdb', 'cluster-habitdb']
    return _run_command(command)

@command
def copyclientsecret():
    '''Copies client secret TODO improve this'''
    getcredentials()
    command = [get_scp_command(), 'jake@hephaestus:/home/jake/Src/secrets/client_secret_712322130843-pi61a3cagb4ic94d5pep77n5tpv4dmf1.apps.googleusercontent.com.json', './app/']
    return _run_command(command)

@command
def build():
    '''Build docker images'''
    copyclientsecret()
    # TODO determine names based on configuration or directory context
    tag = _kubegetnexttag('gcr.io/habitdb/habitdb-www')
    habitdb_www_build_command = ['docker', 'build', '-t', tag, '.']
    _run_command(habitdb_www_build_command)
    tag = _kubegetnexttag('gcr.io/habitdb/kanbanflow_sync')
    kanbanflow_sync_build_command = ['docker', 'build', '-t', tag, 'kanbanflow_sync']
    return _run_command(kanbanflow_sync_build_command)

def _pushtogke(image_name):
    tag = _kubegetnexttag(image_name)
    push_command = ['docker', 'push', tag]
    _run_command(push_command)
    prodtag = '{}:prod'.format(image_name)
    tag_command = ['docker', 'tag', tag, prodtag]
    _run_command(tag_command)
    push_prod_command = ['docker', 'push', prodtag]
    _run_command(push_prod_command)

@command
def pushtogke():
    '''Push docker images to google kubernetes cloud'''
    # TODO only run prerequisites if they aren't met
    build()
    image_name = 'gcr.io/habitdb/habitdb-www'
    _pushtogke(image_name)
    
    image_name = 'gcr.io/habitdb/kanbanflow_sync'
    _pushtogke(image_name)

@command
def applygkeconfig():
    '''Apply updates to google kubernetes engine in the cloud'''
    # TODO only run prerequisites if they aren't met
    pushtogke()
    apply_habitdb_command = ['kubectl', 'apply', '-f', 'deployment/kubernetes/www.yaml']
    _run_command(apply_habitdb_command)

@command
def getpodname():
    '''Get the detailed pod name by label'''
    get_pod_name_command = ['kubectl', 'get', 'pods', '-l', 'name=www', "-o=jsonpath='{.items[].metadata.name}'"]
    result = _run_command(get_pod_name_command, stdout=subprocess.PIPE)
    podname = result.stdout.decode("utf-8", errors='ignore').replace("'", "")
    print(podname)
    return podname

@command
def kubelogs():
    '''Get the logs for a given container'''
    podname = getpodname()
    if not len(sys.argv) > 2:
        print("Error: container name required")
        return

    args = sys.argv[2:]
    containername = args[0]
    kubectl_logs_command = ['kubectl', 'logs', podname, '-c', containername]
    _run_command(kubectl_logs_command)

@command
def kubeexec():
    '''Exec in a given container'''
    podname = getpodname()
    if not len(sys.argv) > 3:
        print("Error: container name and command required")
        return
    
    args = sys.argv[2:]
    containername = args[0]
    exec_command = args[1:]
    kubectl_exec_command = ['kubectl', 'exec', '-it', podname, '-c', containername, '--'] + exec_command
    _run_command(kubectl_exec_command)

@command
def kubegettags():
    '''Get the current tags for a given image'''
    if not len(sys.argv) > 2:
        print("Error: image name required")
        return
    
    args = sys.argv[2:]
    image_name = args[0]
    list_tags_command = ['gcloud', 'container', 'images', 'list-tags', image_name]
    _run_command(list_tags_command)

def _kubegetlatesttagarray(image_name):
    list_tags_command = ['gcloud', 'container', 'images', 'list-tags', image_name, '--limit=1', '--format=value(tags[])']
    result = _run_command(list_tags_command, stdout=subprocess.PIPE)
    latesttags = result.stdout.decode("utf-8", errors='ignore').replace("'", "").split(';')
    split_tags = []
    for tag in latesttags:
        tag_values = [int(i) for i in tag.replace('v', '').split('.') if i.isdigit()]
        split_tags.append(tag_values)
    split_tags = list(sorted(split_tags, reverse=True))
    return split_tags[0]

def _kubegetlatesttag(image_name):
    tag_array = _kubegetlatesttagarray(image_name)
    latest_tag = "v" + ".".join([str(i) for i in tag_array])
    # print(latest_tag)
    return latest_tag

def _kubegetnexttag(image_name):
    tag_array = _kubegetlatesttagarray(image_name)
    tag_array[-1] += 1
    next_tag = "v" + ".".join([str(i) for i in tag_array])
    return "{}:{}".format(image_name, next_tag)

@command
def kubegetlatesttag():
    '''Get the latest tag for a given image'''
    if not len(sys.argv) > 2:
        print("Error: image name required")
        return
    
    args = sys.argv[2:]
    image_name = args[0]
    _kubegetlatesttag(image_name)

@command
def buildpackage():
    '''Build the python package for distribution'''
    build_wheel_command = ['python', 'setup.py', 'sdist', 'bdist_wheel']
    _run_command(build_wheel_command)

@command
def uninstallpackage():
    uninstall_package_command = ['pip', 'uninstall', '-y', 'hey-helper']
    _run_command(uninstall_package_command)

@command
def installpackage():
    buildpackage()
    install_package_command = ['pip', 'install', os.path.realpath('./dist/hey_helper-0.0.3-py3-none-any.whl')]
    _run_command(install_package_command)

def welcome():
    print(r'''
 54  __   __          HEY HELPER SCRIPTS
     \ \ / /
      \ V /  ___      Tips:
      /   \ / _ \     - Alias this script to `hey` for easy running
     / / \ \  __/     - Add one or more ; seperated files to COMPOSE_FILES
    /_/   \_\___|     - Run any command directly with `hey <command> <args>`
''')
    for i, k in enumerate(COMMANDS.keys()):
        sep = '\t'
        if len(k) > 11: sep = ''
        print('{}. {} {} {}'.format(i, k, sep, getattr(COMMANDS[k], '__doc__') or 'Needs docstring'))

    print("\nAlso, these non-interactive commands are available:")
    for k in NONINTERACTIVE.keys():
        print('{} \t {}'.format(k, getattr(NONINTERACTIVE[k], '__doc__') or 'Needs docstring'))

    choice = None
    while not choice or choice.lower() != 'q' and not _command_match(choice):
        choice = input("\nType a number, a command, or `q` to quit: ")

all_commands = dict(COMMANDS)
all_commands.update(NONINTERACTIVE)

def entrypoint():

    if len(sys.argv) < 2:
        welcome()
    else:
        _command_match(sys.argv[1])

if __name__ == '__main__':
    entrypoint()