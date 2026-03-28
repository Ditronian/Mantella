import logging
import os
import signal
import socket
import click
from fastapi import FastAPI
import uvicorn
from src.http.routes.routeable import routeable
from src import utils

class http_server:
    """A simple http server using FastAPI. Can be started using different routes.
    """
    def __init__(self) -> None:
        self.__app = FastAPI()

        ### Deactivate the logging to console by FastAPI
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        def secho(text, file=None, nl=None, err=None, color=None, **styles):
            pass

        def echo(text, file=None, nl=None, err=None, color=None, **styles):
            pass

        click.echo = echo
        click.secho = secho
        ### End of deactivate logging

    @property
    def app(self) -> FastAPI:
        return self.__app

    def start(self, port: int, routes: list[routeable], play_startup_sound: bool, show_debug: bool = False):
        """Starts the server and sets up the provided routes

        Args:
            routes (list[routeable]): The list of routes to start
            show_debug (bool, optional): should debug output be shown
        """
        for route in routes:
            route.add_route_to_server(self.__app)

        if play_startup_sound:
            utils.play_mantella_ready_sound()
        
        self._kill_existing_process_on_port(port)

        logging.log(24, '\nConversations not starting when you select an NPC? See here:')
        logging.log(25, 'https://art-from-the-machine.github.io/Mantella/pages/issues_qna')
        logging.log(24, '\nWaiting for player to select an NPC...')

        uvicorn.run(self.__app, port=port)

    @staticmethod
    def _kill_existing_process_on_port(port: int):
        """Kill any orphaned Mantella process still holding the port."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result != 0:
                return  # Port is free

            # Port is occupied — find and kill the process
            if os.name == 'nt':
                import subprocess
                output = subprocess.check_output(
                    f'netstat -ano | findstr ":{port} "',
                    shell=True, text=True, stderr=subprocess.DEVNULL
                )
                pids = set()
                for line in output.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 5 and 'LISTENING' in line:
                        pids.add(int(parts[-1]))
                current_pid = os.getpid()
                for pid in pids:
                    if pid != current_pid and pid != 0:
                        logging.log(24, f'Killing orphaned Mantella process (PID {pid}) on port {port}...')
                        os.kill(pid, signal.SIGTERM)
            else:
                import subprocess
                output = subprocess.check_output(
                    ['lsof', '-ti', f':{port}'],
                    text=True, stderr=subprocess.DEVNULL
                )
                current_pid = os.getpid()
                for pid_str in output.strip().splitlines():
                    pid = int(pid_str)
                    if pid != current_pid:
                        logging.log(24, f'Killing orphaned Mantella process (PID {pid}) on port {port}...')
                        os.kill(pid, signal.SIGTERM)

            import time
            time.sleep(0.5)
        except Exception:
            pass  # Best effort — if we can't kill it, uvicorn will report the bind error
