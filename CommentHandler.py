#!/usr/bin/env python
# -*- coding: utf-8

import logging
import re
from time import sleep
from urllib.parse import quote, unquote
from random import choice
from os import getcwd
from os.path import join as pjoin
from boardgamegeek import BoardGameGeek as BGG
from boardgamegeek.api import BoardGameGeekNetworkAPI
import boardgamegeek
import praw

log = logging.getLogger(__name__)


class CommentHandler(object):
    def __init__(self, UID, botdb):
        self._botdb = botdb
        self._botname = UID
        self._header = ('^*[{}](/r/r2d8)* ^*issues* ^*a* ^*series* ^*of* ^*sophisticated* '
                        '^*bleeps* ^*and* ^*whistles...*\n\n'.format(self._botname))
        self._footer = ''

        dbpath = pjoin(getcwd(), '{}-bgg.db'.format(self._botname))
        self._bgg = BGG(cache='sqlite://{}?ttl=86400'.format(dbpath))

    def _bggQueryGame(self, name):
        '''Try "name", then if not found try a few other small things in an effort to find it.'''
        name = name.lower().strip()   # GTL extra space at ends shouldn't be matching anyway, fix this.
        if not name:
            return None

        if len(name) > 128:
            log.warn('Got too long game name: {}'.format(name))
            return None

        # Search IDs when name format is '#1234'
        if re.search('^#(\d+)$', name):  
            game = self._bgg.game(name=None, game_id=name[1:])
            if game:
                log.debug('found game {} via searching by ID'.format(name))
                return game

        game = self._bgg.game(name)
        if game:
            return game

        # embedded url? If so, extract.
        log.debug('Looking for embedded URL')
        m = re.search('\[([^]]*)\]', name)
        if m:
            name = m.group(1)
            game = self._bgg.game(name)
            if game:
                return game

        # note: unembedded from here down
        # remove 'the's
        log.debug('removing "the"s')
        tmpname = re.sub('^the ', '', name)
        tmpname = re.sub('\sthe\s', ' ', tmpname)
        if tmpname != name:
            game = self._bgg.game(tmpname)
            if game:
                return game

        # add a "the" at start.
        log.debug('adding "the" at start')
        game = self._bgg.game('The ' + name)
        if game:
            return game

        # various substistutions.
        subs = [
            ('[?!.:,]*', '', 'removing punctuation'),
            ('\sand\s', ' & ', 'and --> &'),
            ('\s&\s', ' and ', '& --> and')
        ]
        for search, sub, logmess in subs:
            log.debug(logmess)
            tmpname = re.sub(search, sub, name)
            if tmpname != name:
                game = self._bgg.game(tmpname)
                if game:
                    return game

        # well OK - let's pull out the heavy guns and use the search API.
        # this will give us a bunch of things to sort through, but hopefully
        # find something.
        return self._bggSearchGame(name)

    def _bggSearchGame(self, name):
        '''Use the much wider search API to find the game.'''
        items = self._bgg.search(name, search_type=BoardGameGeekNetworkAPI.SEARCH_BOARD_GAME, exact=True)
        if items and len(items) == 1:
            log.debug('Found exact match using search().')
            return self._bgg.game(items[0].name)

        # exact match not found, trying sloppy match
        items = self._bgg.search(name, search_type=BoardGameGeekNetworkAPI.SEARCH_BOARD_GAME)
        if items and not len(items):
            log.debug('Found no matches at all using search().')
            return None

        if items and len(items) == 1:
            log.debug('Found one match usinh search().')
            return self._bgg.game(items[0].name)

        if not items:
            return None

        # assume most owned is what people want. Is this good? Dunno.
        most_owned = None
        for i in items:
            game = self._bgg.game(None, game_id=i.id)
            # GTL the lib throws an uncaught exception if BGG assessed too quickly.
            # GTL - this needs to be fixed in the library.
            sleep(1)
            if getattr(game, 'expansion', False):
                log.debug('ignoring expansion')
                continue
            else:
                if not most_owned:
                    most_owned = game
                else:
                    most_owned = game if getattr(game, 'owned', 0) > most_owned.owned else most_owned

        if most_owned:
            return most_owned

        return None

    NO_SORT_KEYWORD = 'nosort'
    DEFAULT_SORT = 'sort_name'
    SORT_FUNCTIONS = {
        'sort_name': lambda g: g.name,
        'sort_year': lambda g: g.year,
        'sort_rank': lambda g: g.rank
        # TODO
    }

    def _findGames(self, items, sort='name'):
        # convert aliases to real names. It may be better to do this after we don't find the
        # game. Oh, well.
        #   I think this might be better behavior, since it makes it easy to
        #   replace findable-but-unlikely results with the more popular result
        #   that was probably intended. -TDHS
        for i in range(len(items)):
            real_name = self._botdb.get_name_from_alias(items[i])
            if real_name:
                items[i] = real_name

        # filter out dups.
        items = list(set(items))
        items = [unquote(b) for b in items]

        games = []
        not_found = []

        seen = set()
        for game_name in items:
            log.info('asking BGG for info on {}'.format(game_name))
            try:
                # game = self._bgg.game(game_name)
                game = self._bggQueryGame(game_name)
                if game:
                    if game.id not in seen:
                        games.append(game)
                    # don't add dups. This can happen when the same game is calledby two valid
                    # names in a post.
                    seen.add(game.id)
                else:
                    not_found.append(game_name)

            except boardgamegeek.exceptions.BoardGameGeekError as e:
                log.error('Error getting info from BGG on {}: {}'.format(game_name, e))
                continue

        # sort by game name because why not?
        if sort and sort in self.SORT_FUNCTIONS:
            fn = self.SORT_FUNCTIONS.get(sort)
            games = sorted(games, key=fn)

        return [games, not_found]

    def _getBoldedEntries(self, comment):
        body = comment.body
        # bolded = re.findall(u'\*\*([^\*]+)\*\*', body)
        # Now I've got two problems.
        bolded = re.findall('\*\*(#?[\w][\w\.\s:\-?$,!\'–&()\[\]]*[\w\.:\-?$,!\'–&()\[\]])\*\*', body, flags=re.UNICODE)
        if not bolded:
            log.warn('Got getinfo command, but nothing is bolded. Ignoring comment.')
            log.debug('comment was: {}'.format(body))
            return
        # we now have all the games.

        if comment.subreddit.display_name.lower() == 'boardgamescirclejerk':
                cjgames = ['Gloomhaven', 'Patchwork', 'Scythe']
                bolded = [choice(cjgames), 'Keyforge', 'Keyforge', 'Keyforge']
        return bolded

    def _getInfoResponseBody(self, comment, gameNames, mode, columns=None, sort=None):
        assert mode
        assert gameNames

        [games, not_found] = self._findGames(gameNames, sort)

        # disallow long mode for 
        if mode == 'long' and len(games) > 6:
            mode = 'short'

        if comment.subreddit.display_name.lower() == 'boardgamescirclejerk':
            not_found = None

        if not_found:
            log.debug('not found: {}'.format(', '.join(not_found)))

        if games:
            log.debug('Found games {}'.format(','.join(['{} ({})'.format(
                g.name, g.year) for g in games])))
        else:
            log.warn('Found no games in comment {}'.format(comment.id))

        log.warning('Using mode {} and columns {}'.format(mode, columns))

        if mode == 'short':
            infos = self._getShortInfos(games)
        elif mode == 'long':
            infos = self._getLongInfos(games)
        elif mode == 'tabular':
            assert columns
            infos = self._getInfoTable(games, columns)
        else:
            infos = self._getStdInfos(games)

        # append not found string if we didn't find a bolded string.
        if not_found:
            not_found = ['[{}](http://boardgamegeek.com/geeksearch.php?action=search'
                         '&objecttype=boardgame&q={}&B1=Go)'.format(
                             n, quote(n)) for n in not_found]
            infos.append('\n\nBolded items not found at BGG (click to search): {}\n\n'.format(', '.join(not_found)))

        response = None
        if len(infos):
            response = self._header + '\n'.join([i for i in infos]) + self._footer
            # TODO: why the copied list?

        return response

    def _getPlayers(self, game):
        if not game.min_players:
            return None

        if game.min_players == game.max_players:
            players = '{} p'.format(game.min_players)
        else:
            players = '{}-{} p'.format(game.min_players, game.max_players)

        return players

    DISPLAY_MODES = [
        'short',
        'standard',
        'long',
        'tabular'
    ]
    DEFAULT_DISPLAY_MODE = 'standard'

    def getInfo(self, comment: praw.models.Comment, subcommands: list, config: dict):
        '''Reply to comment with game information. If replyTo is given reply to original else
        reply to given comment.'''
        if self._botdb.ignore_user(comment.author.name):
            log.info("Ignoring comment by {}".format(comment.author.name))
            return

        replyTo = None

        mode = None
        if len(subcommands) > 0 and subcommands[0].lower() in self.DISPLAY_MODES:
            mode = subcommands[0].lower()
        else:
            mode = self.DEFAULT_DISPLAY_MODE
        columns = subcommands[1:] if mode == 'tabular' else None

        sort = self.DEFAULT_SORT
        if self.NO_SORT_KEYWORD in subcommands:
            sort = None
        else:
            for sort_type in self.SORT_FUNCTIONS.keys():
                if sort_type in subcommands:
                    sort = sort_type
                    break

        footer = '\n' + config['footer'] if 'footer' in config else ''

        bolded = self._getBoldedEntries(comment)
        response = self._getInfoResponseBody(comment, bolded, mode, columns, sort)
        if response:
            if replyTo:
                replyTo.reply(response + footer)
            else:
                comment.reply(response + footer)
            log.info('Replied to info request for comment {}'.format(comment.id))
        else:
            log.warn('Did not find anything to reply to in comment {}'.format(comment.id))

    def _getShortInfos(self, games):
        infos = list()
        for game in games:
            players = self._getPlayers(game)
            info = (' * [**{}**](http://boardgamegeek.com/boardgame/{}) '
                    ' ({}) by {}. '.format(
                        game.name, game.id, game.year, ', '.join(getattr(game, 'designers', 'Unknown'))))
            if players:
                info += '{}; '.format(players)
            if game.playing_time and int(game.playing_time) != 0:
                info += '{} mins '.format(game.playing_time)

            infos.append(info)

        return infos

    def _getStdInfos(self, games):
        infos = list()
        for game in games:
            players = self._getPlayers(game)
            info = ('[**{}**](http://boardgamegeek.com/boardgame/{}) '
                    ' ({}) by {}. {}; '.format(
                        game.name, game.id, game.year, ', '.join(getattr(game, 'designers', 'Unknown')),
                        players))

            if game.playing_time and int(game.playing_time) != 0:
                info += '{} minutes; '.format(game.playing_time)

            if game.image:
                info += '[BGG Image]({}) '.format(game.image)

            info += '\n\n'

            data = ', '.join(getattr(game, 'mechanics', ''))
            if data:
                info += ' * Mechanics: {}\n'.format(data)
            people = 'people' if game.users_rated > 1 else 'person'
            info += ' * Average rating is {}; rated by {} {}. Weight: {}\n'.format(
                game.rating_average, game.users_rated, people, game.rating_average_weight)
            data = ', '.join(['{}: {}'.format(r['friendlyname'], r['value']) for r in game.ranks])
            info += ' * {}\n\n'.format(data)

            log.debug('adding info: {}'.format(info))
            infos.append(info)

        return infos

    ALLOWED_COLUMNS = {
        'year': 'Year Published',
        # 'designers': 'Designers',
        # 'artists': 'Artists',
        'rank': 'BGG Rank',
        'rating': 'Average Rating',
        'score': 'Geek Score (Weighted Rating)',
        'rating_median': 'Median Rating',
        'rating_stddev': 'Rating Standard Deviation',
        'raters': 'Rating Count',
        'owners': 'BGG Owner Count',
        # 'playercount': 'Player Count (min-max)'
        'id': 'BGG ID'
    }

    def _getGameColumn(self, game: boardgamegeek.games.BoardGame, column):
        if column == 'year':
            return str(game.year)
        elif column == 'rank':
            return str(game.boardgame_rank)
        elif column == 'rating':
            return str(game.rating_average)
        elif column == 'score':
            return str(game.rating_bayes_average)
        elif column == 'rating_median':
            return str(game.rating_median)
        elif column == 'rating_stddev':
            return str(game.rating_stddev)
        elif column == 'raters':
            return str(game.users_rated)
        elif column == 'owners':
            return str(game.users_owned)
        elif column == 'id':
            return str(game.id)
        return 'unknown `{}`'.format(column)

    def _getInfoTable(self, games, columns):
        rows = list()
        # build header
        header = 'Game Name'
        alignment = ':--'
        unknownColumns = list()

        for column in columns:
            if column not in self.ALLOWED_COLUMNS:
                log.info('Unknown tabular column {}, skipping'.format(column))
                unknownColumns.append(column)
                continue
            header = header + '|' + self.ALLOWED_COLUMNS[column]
            alignment = alignment + '|:--'

        rows.append(header)
        rows.append(alignment)
        columns = [c for c in columns if c not in unknownColumns]

        # build rows
        for game in games:
            row = '[**{}**](http://boardgamegeek.com/boardgame/{})'.format(game.name, game.id)
            for column in columns:
                row = row + '|' + self._getGameColumn(game, column)
            log.info('adding info: {}'.format(row))
            rows.append(row)

        return rows

    def _getLongInfos(self, games):
        infos = list()
        for game in games:
            players = self._getPlayers(game)
            info = ('Details for [**{}**](http://boardgamegeek.com/boardgame/{}) '
                    ' ({}) by {}. '.format(
                        game.name, game.id, game.year, ', '.join(getattr(game, 'designers', 'Unknown'))))
            if players:
                info += '{}; '.format(players)
            if game.playing_time and int(game.playing_time) != 0:
                info += '{} minutes; '.format(game.playing_time)
            if game.image:
                info += '[BGG Image]({}) '.format(game.image)
            info += '\n\n'

            data = ', '.join(getattr(game, 'mechanics', ''))
            if data:
                info += ' * Mechanics: {}\n'.format(data)
            people = 'people' if game.users_rated > 1 else 'person'
            info += ' * Average rating is {}; rated by {} {}\n'.format(
                game.rating_average, game.users_rated, people)
            info += ' * Average Weight: {}; Number of Weights {}\n'.format(
                game.rating_average_weight, game.rating_num_weights)
            data = ', '.join(['{}: {}'.format(r['friendlyname'], r['value']) for r in game.ranks])
            info += ' * {}\n\n'.format(data)

            info += 'Description:\n\n{}\n\n'.format(game.description)

            if len(games) > 1:
                info += '------'

            log.debug('adding info: {}'.format(info))
            infos.append(info)

        return infos

    def repairComment(self, comment: praw.models.Comment, subcommands: list, config: dict):
        '''Look for maps from missed game names to actual game names. If
        found repair orginal comment.'''
        if self._botdb.ignore_user(comment.author.name):
            log.info("Ignoring comment by {}".format(comment.author.name))
            return
        #
        # The repair is done by replacing the new games names with the old (wrong)
        # games names in the original /u/r2d8 response, then recreating the entire
        # post by regenerating it with the new (fixed) bolded game names. The just replacing
        # the orginal response with the new one.
        #
        log.debug('Got repair response, id {}'.format(comment.id))

        if comment.is_root:
            # error here - this comment should be in response to a u/r2d8 comment.
            log.info('Got a repair comment as root, ignoring.')
            return

        parent = comment.parent()
        if parent.author.name != self._botname:
            log.info('Parent of repair comment is not authored by the bot, ignoring.')
            return

        # Look for patterns of **something**=**somethingelse**. This line creates a dict
        # of something: somethingelse for each one pattern found.
        repairs = {match[0]: match[1] for match in re.findall(
            '\*\*([^\*]+)\*\*=\*\*([^\*]+)\*\*', comment.body)}

        pbody = parent.body
        for wrongName, repairedName in repairs.items():
            # check to see if it's actually a game.
            log.info('Repairing {} --> {}'.format(wrongName, repairedName))
            alias = self._botdb.get_name_from_alias(repairedName)
            tmp_name = alias if alias else repairedName
            tmp_game = self._bggQueryGame(tmp_name)  # with caching it's ok to check twice
            if tmp_game:
                # In the parent body we want to replace [NAME](http://... with **NAME**(http://
                pbody = pbody.replace('[' + wrongName + ']', '**' + tmp_name + '**')
            else:
                log.info('{} seems to not be a game name according to BGG, ignoring.'.format(tmp_name))

        # Now re-bold the not found strings so they are re-searched or re-added to the not found list.
        for nf in re.findall('\[([\w|\s]+)]\(http://boardgamegeek.com/geeksearch.php', pbody):
            pbody += ' **{}**'.format(nf)

        # now re-insert the original command to retain the mode.
        grandparent = parent.parent()
        modes = list()
        if not grandparent:
            log.error('Cannot find original GP post. Assuming normal mode.')
        else:
            modes = re.findall('[getparent|get]info\s(\w+)', grandparent.body)

        targetmode = modes[0] if modes else self.DEFAULT_DISPLAY_MODE

        parent = parent.edit(pbody)
        bolded = self._getBoldedEntries(comment)
        new_reply = self._getInfoResponseBody(parent, bolded, targetmode)

        # should check for Editiable class somehow here. GTL
        log.debug('Replacing bot comment {} with: {}'.format(parent.id, new_reply))
        parent.edit(new_reply)

    def xyzzy(self, comment: praw.models.Comment, subcommands: list, config: dict):
        comment.reply('Nothing happens.')

    def getParentInfo(self, comment: praw.models.Comment, subcommands: list, config: dict):
        '''Allows others to call the bot to getInfo for parent posts.'''
        if self._botdb.ignore_user(comment.author.name):
            log.info("Ignoring comment by {}".format(comment.author.name))
            return

        log.debug('Got getParentInfo comment in id {}'.format(comment.id))

        if comment.is_root:
            # error here - this comment should be in response to a u/r2d8 comment.
            log.info('Got a repair comment as root, ignoring.')
            return

        parent = comment.parent()
        self.getInfo(parent, comment, subcommands=subcommands, config=config)

    def alias(self, comment: praw.models.Comment, subcommands: list, config: dict):
        '''add an alias to the database.'''
        if not self._botdb.is_admin(comment.author.name):
            log.info('got alias command from non admin {}, ignoring.'.format(
                comment.author.name))
            return

        response = 'executing alias command.\n\n'
        for match in re.findall('\*\*([^\*]+)\*\*=\*\*([^\*]+)\*\*', comment.body):
            mess = 'Adding alias to database: "{}" = "{}"'.format(match[0], match[1])
            log.info(mess)
            response += mess + '\n\n'
            self._botdb.add_alias(match[0], match[1])

        comment.reply(response)

    def getaliases(self, comment: praw.models.Comment, subcommands: list, config: dict):
        if self._botdb.ignore_user(comment.author.name):
            log.info("Ignoring comment by {}".format(comment.author.name))
            return

        aliases = self._botdb.aliases()
        response = 'Current aliases:\n\n'
        for name, alias in sorted(aliases, key=lambda g: g[1]):
            response += ' * {} = {}\n'.format(alias, name)

        log.info('Responding to getalaises request with {} aliases'.format(len(aliases)))
        comment.reply(response)

    def expandURLs(self, comment: praw.models.Comment, subcommands: list, config: dict):
        if self._botdb.ignore_user(comment.author.name):
            log.info("Ignoring comment by {}".format(comment.author.name))
            return

        replyTo = None
        mode = None
        if len(subcommands) > 0 and subcommands[0].lower() in self.DISPLAY_MODES:
            mode = subcommands[0].lower()
        else:
            mode = self.DEFAULT_DISPLAY_MODE

        footer = '\n' + config['footer'] if 'footer' in config else ''

        body = comment.body
        urls = [('#' + id) for id in re.findall('boardgamegeek.com/(?:boardgame|thing)/(\d+)', body, flags=re.UNICODE)]

        response = self._getInfoResponseBody(comment, urls, mode)
        log.error('footer {} ({})'.format(footer, type(footer)))
        if response:
            if replyTo:
                replyTo.reply(response + footer)
            else:
                comment.reply(response + footer)
            log.info('Replied to info request for comment {}'.format(comment.id))
        else:
            log.warn('Did not find anything to reply to in comment {}'.format(comment.id))

    def removalRequest(self, comment: praw.models.Comment, subcommands: list, config: dict):
        # if self._botdb.ignore_user(comment.author.name):
        #     log.info("Ignoring comment by {}".format(comment.author.name))
        #     return

        # for now removals are limited to admins
        if not self._botdb.is_admin(comment.author.name):
            log.info('got remove command from non admin {}, ignoring.'.format(
                comment.author.name))
            return
        
        if comment.is_root:
            log.error('removal requested on top-level comment {}, ignoring'.format(comment.id))
            return
        
        botmessage: praw.models.Comment = comment.parent()
        try:
            # delete the post
            botmessage.delete()
            # attempt to unmark the parent as read
            if not botmessage.is_root:
                self._botdb.remove_comment(botmessage.parent)
        except boardgamegeek.exceptions.BoardGameGeekError as e:
            log.error('Error deleting comment {} by {}'.format(original.id, original.author.name))
        return

    # def getThreadInfo(self, comment: praw.models.Comment, subcommands: list, config: dict):
    #     '''get info for all top-level comments in a single thread'''
    #     if self._botdb.ignore_user(comment.author.name):
    #         log.info("Ignoring comment by {}".format(comment.author.name))
    #         return
    #     if (not comment.is_root):
    #         # TODO: respond directly to the user
    #         comment.author.message('r2d8 command error', 
    #             'The `getthreadinfo` command must be used in a top-level comment.\n\nFor questions and issues, please visit /r/r2d8.')
    #         return


    #     for c in comment.parent().comments:
    #         continue # TODO here
