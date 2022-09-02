from invoke import task

def failsafe(callable):
    "Executes the callable, and if not result.ok raises a RemoteWentWrong exception."
    result: Result = callable()
    if not result.ok:
        raise RemoteWentWrong(result.stderr)


def executes_correctly(c: Connection, argument: str) -> bool:
    "returns True if the execution was without error level"
    return c.run(argument, warn=True).ok


def execution_fails(c: Connection, argument: str) -> bool:
    "Returns true if the execution fails based on error level"
    return not executes_correctly(c, argument)



@task
def setup(c):
    print('Setting up reverse proxy...')
    if execution_fails(c,'ls ./logs'):
        c.run('mkdir ./logs')
