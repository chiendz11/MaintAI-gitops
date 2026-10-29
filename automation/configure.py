"""Materialize reviewed local state into manifests. Writes Git files only."""
from .render import render_workloads
from .platform import render_platform_runtimes

if __name__ == '__main__':
    render_workloads()
    render_platform_runtimes()
    print('Desired-state files updated locally. Review the diff and use a PR; nothing was deployed.')
