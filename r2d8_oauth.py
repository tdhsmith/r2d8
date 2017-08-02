import logging
import ConfigParser 

log = logging.getLogger(__name__)

config_file_name = "/home/r2d8/.config/praw.ini"
from pathlib import Path

config_file = Path(config_file_name)
if not config_file.is_file():
    print("Missing praw.ini value with /r/boardgames customized values, stick it in ", config_file_name)
  
def login():
    import praw
    #I'm parsing the config file because praw isn't....  
    config = ConfigParser.ConfigParser()
    config.read(config_file_name)
    # todo: make it error out on file missing
    print("found: ", config.sections(), " if this doens't have bg3po_helper_scripts, you have a generic file")
    section_name = 'r2d8_helper_scripts'
    log.info('logging into reddit')
    r = praw.Reddit(
	client_id=config.get(section_name,'client_id'),
	client_secret=config.get(section_name,'client_secret'),
	user_agent=config.get(section_name,'user_agent'),
	redirect_uri=config.get(section_name,'oauth_redirect_uri'),
	refresh_token=config.get(section_name,'refresh_access_information'),
	scopes=config.get(section_name,'scopes'))
   
    log.info('connected. logging in.')
    return r
