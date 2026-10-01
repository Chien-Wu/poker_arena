"""Apply Unix resource limits in a fresh, single-threaded process, then exec.

Never use preexec_fn in the multi-threaded supervisor: it can deadlock after fork.
"""
from __future__ import annotations
import argparse
import os
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory-mb',type=int,required=True)
    parser.add_argument('--cpu-seconds',type=int,required=True)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command
    if command and command[0]=='--':command=command[1:]
    if not command:parser.error('Missing executable')
    if sys.platform.startswith('linux'):
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(args.memory_mb*1024**2,)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(args.cpu_seconds,)*2)
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
    os.execvpe(command[0],command,os.environ)

if __name__=='__main__':main()
