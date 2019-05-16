# -*- coding: utf-8 -*-
"""
    choppy.notification.messenger
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A module that handles messaging of workflow results.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

from __future__ import unicode_literals
import smtplib
import os
import logging
from email.mime.text import MIMEText
from string import Template
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from choppy.config import get_global_config
from ratelimit import rate_limited

__author__ = "Amr Abouelleil"

global_config = get_global_config()
logger = logging.getLogger(__name__)
ONE_MINUTE = 60


class Messenger(object):
    """A class for generating and sending messages with workflow results to users.
    """

    def __init__(self, user):
        email_domain = global_config.get('email', 'email_domain')
        sender_user = global_config.get('email', 'sender_user')
        self.user_email = "{}@{}".format(user, email_domain)
        self.sender = "{}@{}".format(sender_user, email_domain)

    def compose_email(self, content_dict):
        """Composes an e-mail to be sent containing workflow ID, result of the workflow, and workflow metadata. # noqa

        :param content_dict: A dictionary of key/value pairs that fulfill the requirements of email.template. The keys are: workflow_id, user, status, and metadata.
        :return: A MIMEMultipart message object.
        """
        subject = "Workflow ({}) {}".format(
            content_dict['workflow_id'], content_dict['status'])
        msg = MIMEMultipart(From=self.sender, To=self.user_email, Date=formatdate(localtime=True),
                            Subject=subject)
        msg["Subject"] = subject
        template = open(os.path.join(global_config.resource_dir, 'email.template'), 'r')
        src = Template(template.read())
        text = src.safe_substitute(content_dict)
        msg.attach(MIMEText(text, 'html'))
        template.close()
        return msg

    @rate_limited(300, ONE_MINUTE)
    def send_email(self, msg, user=None):
        """Sends an e-mail to recipients using the localhosts smtp server.

        :param msg: A MIMEMultipart message object.
        :return: None
        """
        if not user:
            user = self.user_email

        try:
            email_smtp_server = global_config.get('email', 'email_smtp_server')
            sender_password = global_config.get('email', 'sender_password')
            sender_user = global_config.get('email', 'sender_user')
            mailer = smtplib.SMTP_SSL(email_smtp_server)
            mailer.login(sender_user, sender_password)
            mailer.sendmail(self.sender, user, msg.as_string())
            logger.info("Send email to %s successfully." % user)
        except Exception as e:
            logger.warn("Can't send email to %s" % user)
            logger.warn(str(e))
