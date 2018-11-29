import sqlite3
import logging

log = logging.getLogger(__name__)

class BotDatabase(object):
    def __init__(self, path):
        super(BotDatabase, self).__init__()
        self._connection = sqlite3.connect(path)

        stmt = 'SELECT name FROM sqlite_master WHERE type="table" AND name="comments"'
        q = self._connection.execute(stmt).fetchall()
        if not q:
            log.info('Creating comments table.')
            self._connection.execute('CREATE table comments (id text)')

        stmt = 'SELECT name FROM sqlite_master WHERE type="table" AND name="aliases"'
        q = self._connection.execute(stmt).fetchall()
        if not q:
            log.info('Creating aliases table.')
            self._connection.execute('CREATE table aliases (gamename text, alias text)')

            # known aliases
            gameNameMap = {
                'Dead of Winter': 'Dead of Winter: A Crossroads Game',
                'Pathfinder': 'Pathfinder Adventure Card Game: Rise of the Runelords - Base Set',
                'Descent 2': 'Descent: Journeys in the Dark (Second Edition)',
                'Seven Wonders': '7 Wonders',
                'Caverna': 'Caverna: The Cave Farmers'
            }

            for a, g in gameNameMap.items():
                log.info('adding alias {} == {} to database'.format(a, g))
                self.add_alias(a, g)

        stmt = 'SELECT name FROM sqlite_master WHERE type="table" AND name="bot_admins"'
        q = self._connection.execute(stmt).fetchall()
        if not q:
            log.info('Creating bot_admins table.')
            self._connection.execute('CREATE table bot_admins (ruid text)')
            for a in ['r2d8']:
                log.info('Adding {} as admin'.format(a))
                self._connection.execute('INSERT INTO bot_admins VALUES (?)', (a,))

        stmt = 'SELECT name FROM sqlite_master WHERE type="table" AND name="ignore"'
        q = self._connection.execute(stmt).fetchall()
        if not q:
            self._connection.execute('CREATE table ignore (uid text)')
            log.info('Created ignore table.')
            pass

        self._connection.commit()

    def add_comment(self, comment):
        log.debug('adding comment {} to database'.format(comment.id))
        comment.mark_read()
        self._connection.execute('INSERT INTO comments VALUES(?)', (comment.id,))
        self._connection.commit()

    def remove_comment(self, comment):
        log.debug('removing comment {} from database'.format(comment.id))
        comment.mark_unread()
        self._connection.execute('DELETE FROM comments WHERE id = (?)', (comment.id,))
        self._connection.commit()

    def comment_exists(self, comment):
        cmd = 'SELECT COUNT(*) FROM comments WHERE id=?'
        count = self._connection.execute(cmd, (comment.id,)).fetchall()[0]
        return count and count[0] > 0

    def add_alias(self, alias, name):
        gname = self.get_name_from_alias(alias)
        if not gname:
            self._connection.execute('INSERT INTO aliases VALUES (?, ?)', (name, alias))
            self._connection.commit()

    def get_name_from_alias(self, name):
        cmd = 'SELECT gamename FROM aliases where alias=?'
        rows = self._connection.execute(cmd, (name,)).fetchall()
        return rows[0][0] if rows else None

    def aliases(self):
        cmd = 'SELECT * FROM aliases' 
        rows = self._connection.execute(cmd).fetchall()
        return [] if not rows else rows

    def is_admin(self, uid):
        cmd = 'SELECT COUNT(ruid) FROM bot_admins where ruid=?'
        rows = self._connection.execute(cmd, (uid,)).fetchall()
        if not rows:
            return False

        return False if rows[0][0] == 0 else True

    def ignore_user(self, uid):
        cmd = 'SELECT COUNT(uid) FROM ignore where uid=?'
        rows = self._connection.execute(cmd, (uid,)).fetchall()
        if not rows:
            return False

        return False if rows[0][0] == 0 else True
