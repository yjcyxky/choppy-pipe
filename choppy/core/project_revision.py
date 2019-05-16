# -*- coding: utf-8 -*-
"""
    choppy.core.project_revision
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Module to keep track of all project files.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import git
import os
from getpass import getpass


class Git:
    def __init__(self):
        self.path = None
        self.repo = None
        self.remote = None

    def init_repo(self, path):
        self.path = path
        # Add default git ignore files.
        git_ignore = os.path.join(self.path, '.gitignore')
        if not os.path.isfile(git_ignore):
            with open(git_ignore, 'w') as f:
                f.write('.git/*')
        self.repo = git.Repo.init(path=self.path)

    def _set_auth(self, username):
        os.environ['GIT_USERNAME'] = username
        os.environ['GIT_PASSWORD'] = getpass()

    def clone_from(self, url, to_path, branch='master', username=None):
        if not branch:
            branch = 'master'

        if username:
            self._set_auth(username)

        git.Repo.clone_from(url, to_path, branch=branch)

    def _check_repo(self, msg):
        if self.repo is None:
            raise Exception(msg)

    def _check_remote(self, msg):
        if self.remote is None:
            raise Exception(msg)

    def add_remote(self, url, name='origin', username=None):
        self._check_repo(
            "Attempting to add remote to git repo but the repo doesn't exist."
            " You need to call init_repo firstly.")
        if username:
            self._set_auth(username)
        self.remote = self.repo.create_remote(name=name, url=url)

    def _get_all_files(self):
        previous_dir = os.getcwd()
        os.chdir(self.path)

        all_files = []
        for root, dirnames, filenames in os.walk(os.getcwd()):
            if '.git' in dirnames:
                dirnames.remove('.git')

            for filename in filenames:
                all_files.append(os.path.join(root, filename))

        os.chdir(previous_dir)
        return all_files

    def add(self):
        self._check_repo(
            "Attempting to add but the repo doesn't exist. "
            "You need to call init_repo firstly.")
        self.repo.index.add(items=self._get_all_files())

    def commit(self, msg="Add new files."):
        self._check_repo(
            "Attempting to commit but the repo doesn't exist. "
            "You need to call init_repo firstly.")
        if self.is_dirty():
            self.repo.index.add(items=self._get_all_files())
            self.repo.index.commit(msg)

    def push(self):
        self._check_remote("Attempting to push repo to remote but the remote repo doesn't exist."
                           " You need to call add_remote firstly.")
        self.remote.push()

    def is_dirty(self):
        self._check_repo(
            "Attempting to get status of git repo but the repo doesn't exist. "
            "You need to call init_repo firstly.")
        return self.repo.is_dirty() or self.repo.untracked_files

    def status(self):
        self._check_repo(
            "Attempting to get status of git repo but the repo doesn't exist. "
            "You need to call init_repo firstly.")
        return self.repo.is_dirty()

    def current_repo(self):
        self._check_repo(
            "Attempting to get current repo but the repo doesn't exist. "
            "You need to call init_repo firstly.")
        return self.path
