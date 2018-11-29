import argparse
import praw
import logging
import re
from time import sleep
from html.parser import HTMLParser 
from argParseLog import addLoggingArgs, handleLoggingArgs
from BotDatabase import BotDatabase
from CommentHandler import CommentHandler

from r2d8_oauth import login as oauth_login

log = logging.getLogger(__name__)

def start_bot():
    ap = argparse.ArgumentParser()
    botname = 'r2d8'
    dbname = '{}-bot.db'.format(botname)
    sleepTime = 5

    ap.add_argument(
        '-d',
        '--database',
        help='The bot database. Default is {}'.format(dbname),
        default='{}'.format(dbname))
    ap.add_argument(
        '-r',
        '--read',
        help='Mark all existing queries as read without responding, then exit.',
        action='store_true', # default is false, flag present => true
        dest='mark_read')
    ap.add_argument(
        '-s',
        '--sleep',
        help='Time to sleep between API checks. Default is {} seconds.'.format(sleepTime),
        default=sleepTime,
        type=int)
    ap.add_argument(
        '-o',
        '--once',
        help='Run once and quit', 
        action='store_true')
    ap.add_argument(
        '-t',
        '--target',
        help='Run the tool on a specific comment ID target',
        default=None)
    ap.add_argument(
        '--command',
        help='When run in target mode, overrides/simulates a specific bot command',
        default=None)
    ap.add_argument(
        '-c',
        '--config',
        help='Config file location for PRAW',
        default=None)
    ap.add_argument(
        '-f',
        '--footer',
        help='Custom footer to append to the message',
        default='')
    addLoggingArgs(ap)
    args = ap.parse_args()
    handleLoggingArgs(args)

    dbname = args.database if args.database else dbname
    sleepTime = args.sleep if args.sleep else sleepTime

    hp = HTMLParser()

    # quiet requests
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("prawcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    reddit = oauth_login(config_file_path = args.config) if args.config else oauth_login()

    bdb = BotDatabase(args.database)
    log.info('Bot database opened/created.')
    ch = CommentHandler(botname, bdb)
    log.info('Comment/notification handler created.')

    CMDMAP = {
        'getinfo': ch.getInfo,
        'repair': ch.repairComment,
        'xyzzy': ch.xyzzy,
        'alias': ch.alias,
        'getaliases': ch.getaliases,
        'getparentinfo': ch.getParentInfo,
        'getinfoparent': ch.getParentInfo,
#        'getthreadinfo': ch.getThreadInfo,
        'expandurls': ch.expandURLs,
        'tryagain': ch.removalRequest,
        'shame': ch.removalRequest
    }
    BOTCMD_REGEX = re.compile('/?u/{}\s(\w+)(\s\w+)*'.format(botname), re.IGNORECASE)

    CONFIG = {
        'footer': args.footer
    }

    # target is like once, but we don't even need to scan for mentions
    if args.target:
        log.info('Executing specific target')
        comment = reddit.comment(args.target)
        if not bdb.comment_exists(comment):
            bdb.add_comment(comment)
            if args.mark_read:
                return
        commands = [args.command.split()] if args.command else BOTCMD_REGEX.findall(comment.body)
        for cmd in commands:
            primaryCommand = cmd[0].lower()
            if primaryCommand in CMDMAP:
                comment.body = hp.unescape(comment.body)
                CMDMAP[primaryCommand](
                    comment,
                    subcommands=cmd[1:],
                    config=CONFIG)
            else:
                log.info('Got unknown command: {}'.format(primaryCommand))
        return

    log.info('Waiting for new PMs and/or notifications.')
    while True:
        try:
            for comment in list(reddit.inbox.mentions()) + list(reddit.inbox.unread()):
                log.debug('got {}'.format(comment.id))
                if not bdb.comment_exists(comment):
                    bdb.add_comment(comment)
                    if args.mark_read:
                        continue

                    for cmd in BOTCMD_REGEX.findall(comment.body):
                        primaryCommand = cmd[0].lower()
                        if primaryCommand in CMDMAP:
                            comment.body = hp.unescape(comment.body)
                            CMDMAP[primaryCommand](
                                comment,
                                subcommands=cmd[1:],
                                config=CONFIG)
                        else:
                            log.info('Got unknown command: {}'.format(primaryCommand))

        except Exception as e:
            log.error('Caught exception: {}'.format(e))

        # get_mentions is non-blocking
        if args.mark_read or args.once:
            exit(0)

        sleep(sleepTime)

if "__main__" == __name__:
    start_bot()
