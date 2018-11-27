import argparse
import praw
import logging
import re
from time import sleep
from HTMLParser import HTMLParser 
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
        u'-d',
        u'--database',
        help=u'The bot database. Default is {}'.format(dbname),
        default=u'{}'.format(dbname))
    ap.add_argument(
        '-r',
        '--read',
        help='Mark all existing queries as read without responding, then exit.',
        action='store_true', # default is false, flag present => true
        dest='mark_read')
    ap.add_argument(
        '-s',
        '--sleep',
        help=u'Time to sleep between API checks. Default is {} seconds.'.format(sleepTime),
        default=sleepTime,
        type=int)
    ap.add_argument(
        '-o',
        '--once',
        help=u'Run once and quit', 
        action='store_true')
    ap.add_argument(
        '-t',
        '--target',
        help=u'Run the tool on a specific comment ID target',
        default=None)
    ap.add_argument(
        '-c',
        '--config',
        help=u'Config file location for PRAW',
        default=None)
    addLoggingArgs(ap)
    args = ap.parse_args()
    handleLoggingArgs(args)

    dbname = args.database if args.database else dbname
    sleepTime = args.sleep if args.sleep else sleepTime

    hp = HTMLParser()

    # quiet requests
    logging.getLogger(u"requests").setLevel(logging.WARNING)
    logging.getLogger(u"prawcore").setLevel(logging.WARNING)
    logging.getLogger(u"urllib3").setLevel(logging.WARNING)

    reddit = oauth_login(config_file_path = args.config) if args.config else oauth_login()

    bdb = BotDatabase(args.database)
    log.info(u'Bot database opened/created.')
    ch = CommentHandler(botname, bdb)
    log.info(u'Comment/notification handler created.')

    CMDMAP = {
        u'getinfo': ch.getInfo,
        u'repair': ch.repairComment,
        u'xyzzy': ch.xyzzy,
        u'alias': ch.alias,
        u'getaliases': ch.getaliases,
        u'getparentinfo': ch.getParentInfo,
        u'getinfoparent': ch.getParentInfo,
        u'getthreadinfo': ch.getThreadInfo
    }
    BOTCMD_REGEX = re.compile(u'/?u/{}\s(\w+)'.format(botname), re.IGNORECASE)

    # target is like once, but we don't even need to scan for mentions
    if args.target:
        log.info(u'Executing specific target')
        comment = reddit.comment(args.target)
        if not bdb.comment_exists(comment):
            bdb.add_comment(comment)
            if args.mark_read:
                return
        for cmd in [c.lower() for c in BOTCMD_REGEX.findall(comment.body)]:
            if cmd in CMDMAP:
                comment.body = hp.unescape(comment.body)
                CMDMAP[cmd](comment)
            else:
                log.info(u'Got unknown command: {}'.format(cmd))
        return

    log.info(u'Waiting for new PMs and/or notifications.')
    while True:
        try:
            for comment in list(reddit.inbox.mentions()) + list(reddit.inbox.unread()):
                log.debug(u'got {}'.format(comment.id))
                if not bdb.comment_exists(comment):
                    bdb.add_comment(comment)
                    if args.mark_read:
                        continue

                    for cmd in [c.lower() for c in BOTCMD_REGEX.findall(comment.body)]:
                        if cmd in CMDMAP:
                            comment.body = hp.unescape(comment.body)
                            CMDMAP[cmd](comment)
                        else:
                            log.info(u'Got unknown command: {}'.format(cmd))

        except Exception as e:
            log.error(u'Caught exception: {}'.format(e))

        # get_mentions is non-blocking
        if args.mark_read or args.once:
            exit(0)

        sleep(sleepTime)

if "__main__" == __name__:
    start_bot()
