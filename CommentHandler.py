#!/usr/bin/env python

import logging
import re
import yaml
from random import choice
from os import getcwd
from os.path import join as pjoin
from boardgamegeek import BoardGameGeek as BGG
import boardgamegeek

log = logging.getLogger(__name__)


class CommentHandler(object):
    def __init__(self, UID, botdb):
        self._botdb = botdb
        self._botname = UID
        self._header = '*^({} issues a series of sophisticated bleeps and whistles...)*\n\n'.format(self._botname)
        self._footer = ('\n\n'
                        '-------------\n'
                        '^({} is a bot. Looks a little like a trash can, but you shouldn\'t hold that against him.) '
                        '[^Submit ^questions, ^abuse, ^and ^bug ^reports ^here.](/r/r2d8)'.format(self._botname))

        dbpath = pjoin(getcwd(), '{}-bgg.db'.format(self._botname))
        self._bgg = BGG(cache='sqlite://{}?ttl=86400'.format(dbpath))

    def _getInfoResponseBody(self, comment, mode=None):
        body = comment.body.encode('utf-8')
        bolded = [b for b in re.findall('\*\*([^\*]+)\*\*', body)]

        if not bolded:
            log.warn('Got getinfo command, but nothing is bolded. Ignoring comment.')
            log.debug('comment was: {}'.format(body))
            return

        # filter out dups.
        bolded = list(set(bolded))

        # convert aliases to real names. It may be better to do this after we don't find the 
        # game. Oh, well.
        for i in xrange(len(bolded)):
            real_name = self._botdb.get_alias(bolded[i])
            if real_name:
                bolded[i] = real_name
    
        games = []
        not_found = []

        if comment.subreddit.display_name.lower() == 'boardgamescirclejerk':
            old_bolded = bolded[:]
            bolded = choice([
                ['Dead of Winter: A Crossroads Game'],
                ['Ginkgopolis'],
                ['Machi Koro']
            ])

        for game_name in bolded:
            log.info('asking BGG for info on {}'.format(game_name))
            try:
                games_of_this_name = []
                for title in self._bgg.search(game_name):
                    if title.type == 'boardgame':
                        if title.name == game_name:
                            # search returns a game even if the alternate game name is the name.
                            tmp_game = self._bgg.game(name=None, game_id=title.id)
                            if tmp_game.name.encode('utf-8') == game_name:
                                games_of_this_name.append(self._bgg.game(name=None,
                                                                         game_id=title.id))
   
                if games_of_this_name:
                    games_of_this_name.sort(key=lambda g: g.year, reverse=True)
                    games += games_of_this_name
    
            except boardgamegeek.exceptions.BoardGameGeekError:
                log.error('Error getting info from BGG on {}'.format(game_name))
                continue
    
        # we now have all the games. 
        mode = 'short' if len(games) > 6 else mode
        not_found = list(set(bolded) - set([game.name for game in games]))

        if comment.subreddit.display_name.lower() == 'boardgamescirclejerk':
            not_found = old_bolded[:]

        if not_found:
            log.debug('not found: {}'.format(', '.join(not_found)))

        if games:
            log.debug('Found games {}'.format(','.join(['{} ({})'.format(
                game.name.encode('utf-8'), game.year) for game in games])))
        else:
            log.warn('Found no games in comment {}'.format(comment.id))

        # get the information for each game in a nice tidy list of strings.
        # get the mode if given. Can be short or long or normal. Default is normal.
        if not mode:
            m = re.search('getinfo\s(\w+)', body)
            if m:
                mode = m.group(1) if m.group(1) in ['short', 'long'] else mode

        if mode == 'short':
            infos = self._getShortInfos(games)
        elif mode == 'long':
            infos = self._getLongInfos(games)
        else:
            infos = self._getStdInfos(games)

        # append not found string if we didn't find a bolded string.
        if not_found:
            not_found = ['[{}](http://boardgamegeek.com/geeksearch.php?action=search&objecttype=boardgame&q={}&B1=Go)'.format(
                n, n) for n in not_found]
            if mode == 'short':
                infos.append('\n\n-----\nBolded items not found at BGG: {}\n\n'.format(
                    ', '.join(not_found)))
            else:
                infos.append('Bolded items not found at BGG: {}\n\n'.format(', '.join(not_found)))

        response = None
        if len(infos):
            if mode == 'short':
                response = self._header + '\n'.join([i for i in infos]) + self._footer
            else:
                response = self._header + '-----\n'.join([i for i in infos]) + self._footer

        return response

    def getInfo(self, comment, replyTo=None, mode=None):
        '''Reply to comment with game information. If replyTo isot given reply to original else
        reply to given comment.'''
        response = self._getInfoResponseBody(comment, mode)
        if response:
            if replyTo:
                replyTo.reply(response)
            else:
                comment.reply(response)
            log.info('Replied to info request for comment {}'.format(comment.id))
        else:
            log.warn('Did not find anything to reply to in comment'.format(comment.id))

    def _getShortInfos(self, games):
        infos = list()
        for game in games:                            
            infos.append(' * [**{}**](http://boardgamegeek.com/boardgame/{}) '
                         ' ({}) by {}'.format(game.name.encode('utf-8'), game.id, game.year,
                                              ', '.join(getattr(game, 'designers', 'Unknown')).encode('utf-8')))
        return infos

    def _getStdInfos(self, games):
        infos = list()
        for game in games:
            info = ('Details for [**{}**](http://boardgamegeek.com/boardgame/{}) '
                    ' ({}) by {}\n\n'.format(game.name.encode('utf-8'), game.id, game.year,
                                             ', '.join(getattr(game, 'designers', 'Unknown')).encode('utf-8')))
            data = ', '.join(getattr(game, 'mechanics', ''))
            if data:
                info += ' * Mechanics: {}\n'.format(data.encode('utf-8'))
            people = 'people' if game.users_rated > 1 else 'person'
            info += ' * Average rating is {}; rated by {} {}\n'.format(
                game.rating_average, game.users_rated, people)
            data = ', '.join(['{}: {}'.format(r['friendlyname'], r['value']) for r in game.ranks])
            info += ' * {}\n\n'.format(data)
    
            log.debug('adding info: {}'.format(info))
            infos.append(info)
    
        return infos

    def _getLongInfos(self, games):
        infos = list()
        for game in games:
            info = ('Details about [**{}**](http://boardgamegeek.com/boardgame/{}) '
                    ' ({}) by {}\n\n'.format(game.name.encode('utf-8'), game.id, game.year,
                                             ', '.join(getattr(game, 'designers', 'Unknown')).encode('utf-8')))
            data = ', '.join(getattr(game, 'mechanics', ''))
            if data:
                info += ' * Mechanics: {}\n'.format(data.encode('utf-8'))
            people = 'people' if game.users_rated > 1 else 'person'
            info += ' * Average rating is {}; rated by {} {}\n'.format(
                game.rating_average, game.users_rated, people)
            data = ', '.join(['{}: {}'.format(r['friendlyname'], r['value']) for r in game.ranks])
            info += ' * {}\n\n'.format(data)
   
            info += 'Description:\n\n{}\n\n'.format(game.description.encode('utf-8'))

            log.debug('adding info: {}'.format(info))
            infos.append(info)

        return infos

    def repairComment(self, comment):
        '''Look for maps from missed game names to actual game names. If 
        found repair orginal comment.'''
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

        parent = comment.reddit_session.get_info(thing_id=comment.parent_id)
        if parent.author.name != self._botname:
            log.info('Parent of repair comment is not authored by the bot, ignoring.')
            return 

        # Look for patterns of **something**=**somethingelse**. This line creates a dict 
        # of something: somethingelse for each one pattern found. 
        repairs = {match[0]: match[1] for match in re.findall(
            '\*\*([^\*]+)\*\*=\*\*([^\*]+)\*\*', comment.body.encode('utf-8'))}
        
        pbody = parent.body.encode('utf-8')
        for wrongName, repairedName in repairs.iteritems():
            # check to see if it's actually a game.
            log.info('Repairing {} --> {}'.format(wrongName, repairedName))
            tmp_game = self._bgg.game(name=repairedName)  # with caching it's ok to check twice
            if tmp_game:
                # In the parent body we want to replace [NAME](http://... with **NAME**(http://
                pbody = pbody.replace('[' + wrongName + ']', '**' + repairedName + '**')
            else:
                log.info('{} seems to not be a game name according to BGG, ignoring.'.format(repairedName))

        # Now re-bold the not found strings so they are re-searched or re-added to the not found list.
        for nf in re.findall('\[([\w|\s]+)]\(http://boardgamegeek.com/geeksearch.php', pbody):
            pbody += ' **{}**'.format(nf)

        # now re-insert the original command to retain the mode. 
        grandparent = parent.reddit_session.get_info(thing_id=parent.parent_id)
        modes = list()
        if not grandparent:
            log.error('Cannot find original GP post. Assuming normal mode.')
        else:
            modes = re.findall('[getparent|get]info\s(\w+)', grandparent.body.encode('utf-8'))

        if modes:
            log.debug('Recreating {} mode from the GP.'.format(modes[0]))
            pbody += ' /u/{} getinfo {}'.format(self._botname, modes[0])
        else:
            pbody += ' /u/{} getinfo'.format(self._botname)

        parent = parent.edit(pbody)
        new_reply = self._getInfoResponseBody(parent)

        # should check for Editiable class somehow here. GTL
        log.debug('Replacing bot comment {} with: {}'.format(parent.id, new_reply))
        parent.edit(new_reply)

    def xyzzy(self, comment):
        comment.reply('Nothing happens.')

    def alias(self, comment):
        '''add an alias to the database.'''
        pass

    def getParentInfo(self, comment):
        '''Allows others to call the bot to getInfo for parent posts.'''
        log.debug('Got getParentInfo comment in id {}'.format(comment.id))

        if comment.is_root:
            # error here - this comment should be in response to a u/r2d8 comment.
            log.info('Got a repair comment as root, ignoring.')
            return

        m = re.search('getparentinfo\s(\w+)', comment.body.encode('utf-8'))
        mode = None
        if m:
            mode = 'short' if m.group(1) == 'short' else 'long'


        parent = comment.reddit_session.get_info(thing_id=comment.parent_id)
        self.getInfo(parent, comment, mode)

    # This is harder than it seems. Need to query BGG by ID. 
    # def chooseDuplicate(self, comment):
    #     log.debug('Got choose duplicate response, id {}'.format(comment.id))

    #     if comment.is_root:
    #         # error here - this comment should be in response to a u/r2d8 comment.
    #         log.info('Got a repair comment as root, ignoring.')
    #         return

    #     # parent is the original response from the bot with the information.
    #     parent = comment.reddit_session.get_info(thing_id=comment.parent_id)
    #     if parent.author.name != self._botname:
    #         log.info('Parent of repair comment is not authored by the bot, ignoring.')
    #         return

    #     # keepers == [(Dominion, 2004), (SET, 1994), ... ]
    #     keepers = re.findall('\*\*([^\*]+)\s\((\d+\))\*\*', comment.body.encode('utf-8'))

    #     pbody = parent.body.encode('utf-8')
    #     for dups in dupchoices:
    #         # losers == ['**Domnion (2013)**', '**Dominion (1992)**, ...]
    #         losers = re.findall('(\*\*{} \(\d+\)\*\*)'.format(dups[0]))
    #         for loser in losers:
    #             pbody.replace(loser, '')

    #     # now add the keepers back in.
    #     for keeper in keepers:
    #         pbody += '**{} ({})**'.format(keeper[0], keeper[1])

    #     # now re-insert the original command to retain the mode. 
    #     grandparent = parent.reddit_session.get_info(thing_id=parent.parent_id)
    #     modes = list()
    #     if not grandparent:
    #         log.error('Cannot find original GP post. Assuming normal mode.')
    #     else:
    #         modes = re.findall('[getparent|get]info\s(\w+)', grandparent.body.encode('utf-8'))

    #     if modes:
    #         log.debug('Recreating {} mode from the GP.'.format(modes[0]))
    #         pbody += ' /u/{} getinfo {}'.format(self._botname, modes[0])
    #     else:
    #         pbody += ' /u/{} getinfo'.format(self._botname)

    #     new_reply = self._getInfoResponseBody(parent)

    #     # should check for Editiable class somehow here. GTL
    #     log.debug('Replacing bot comment {} with: {}'.format(parent.id, new_reply))
    #     parent.edit(new_reply)
