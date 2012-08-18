# encoding: utf-8
# Useful decorators

from fabric.api import *

# These variables must be defined in the actual fabfile.py for the proxy decorators:
# env.proxy_server = 'proxy.com.br'     Address of the proxy server intermediating the executation
# env.proxy_home   = '/home/me/fabric'  Location, at the proxy server, where fabfily.py will reside
# env.proxy_hosts  = []                 List of hosts and/or roles specified for this session - will
# env.proxy_roles  = []                   be included in the fab command executed at the proxy server

def _is_running_on_proxy():
    """
    Returns True if this fabfile is being run on the proxy server.
    """
    return env.real_fabfile.find(env.proxy_home) < 0

def _run_on_proxy(role=None, host=None):
    """
    Decorator that creates the actual decorator to route tasks through proxy.
    This is necessary in order to be able to pass parameters to the actual decorator.

    Usage:

        @hosts(env.proxy_server)
        @_run_on_proxy([host='somehost'|role='somerole'])
        def mytask():

    Each task must be surrounded by a @hosts decorator specifying the proxy server,
    so the task will be initially run at the proxy.

    Then the @_run_on_proxy decorator can be used with or without specifying the actual
    servers where the task should be run. If no servers are specifyied, then the lists
    env.proxy_roles or env.proxy_hosts should be previously populated by some other task.
    """
    def actual_decorator(task):
        """
        Actual decorator that routes the task to be run on proxy.
        """
        def wrapper(*args, **kwargs):
            """
            Wrapper that checks if command is being run on proxy server.
            If it is, invokes fab again specifying some other server.
            If it is already being run on some other server, just execute the task.
            """
            if _is_running_on_proxy():
                # There are several ways to specify in which other server this
                # task is to be run. Hosts/roles specified by the decorator itself
                # have higher priority.

                # If a role or host parameter was specified for the decorator, use them
                if role:
                    kwargs['role'] = role
                elif host:
                    kwargs['host'] = host
                # If some previous task populated the lists env.proxy_roles or proxy_hosts, use them
                elif env.proxy_roles:
                    kwargs['role'] = env.proxy_roles[0]
                elif env.proxy_hosts:
                    kwargs['host'] = env.proxy_hosts[0]

                with cd(env.proxy_home):
                    arguments = []
                    if args:
                        arguments.append(','.join(args))
                    if kwargs:
                        arguments.append(','.join(['%s=%s' % (k,v) for k,v in kwargs.items()]))
                    if args or kwargs:
                        run('fab %s:%s' % (task.__name__, ','.join(arguments)))
                    else:
                        run('fab %s' % task.__name__)
            else:
                task(*args, **kwargs)

        return wrapper

    return actual_decorator
