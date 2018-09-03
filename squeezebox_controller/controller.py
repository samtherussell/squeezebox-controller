import requests
import json
from functools import wraps, partial

class UserException(Exception):
  pass
  
def _cache_player(f):
  @wraps(f)
  def cached_f(self, details):
    if (not self.cached_player == None) and ("player" not in details or details["player"] == "$player"):
      details["player"] = self.cached_player
    else:
      self.cached_player = details['player']
    return f(self, details)
  return cached_f
  
def _cache_player_custom(self, f):
  @wraps(f)
  def cached_f(helper, details={}):
    if (not self.cached_player == None) and ("player" not in details or details["player"] == "$player"):
      details["player"] = self.cached_player
    else:
      self.cached_player = details['player']
    return f(helper, details)
  return cached_f
  
class SqueezeBoxController:

  commands = {
    "PLAY": ["play"],
    "PAUSE": ["pause"],
    "POWER ON": ["power", "1"],
    "POWER OFF": ["power", "0"],
    "VOLUME UP": ["mixer","volume","+10"],
    "VOLUME DOWN": ["mixer","volume","-10"],
    "SLEEP": ["sleep","300"],
    "SLEEP SONG": ["jiveendoftracksleep"],
    "SKIP": ["playlist","index","+1"],
    "PREVIOUS": ["playlist","index","-1"],
    "UNSYNC": ["sync","-"],
    "SHUFFLE OFF": ["playlist","shuffle",0],
    "SHUFFLE SONGS": ["playlist","shuffle",1],
    "SHUFFLE ALBUMS": ["playlist","shuffle",2],
    "REPEAT OFF": ["playlist","repeat",0],
    "REPEAT SONG": ["playlist","repeat",1],
    "REPEAT PLAYLIST": ["playlist","repeat",2]
  }

  cached_player = None

  search_types = {
    "SONG": "track",
    "ALBUM": "album",
    "ARTIST": "contributor"
  }
  default_search_type = "SONG"

  queries = {
    "VOLUME": lambda info: "The volume is at %d percent"%(info['mixer volume']),
    "NOW PLAYING": lambda info: info['playlist_loop'][0]['title'] + ' by ' + info['playlist_loop'][0]['artist'] \
                        if 'playlist_loop' in info and len(info['playlist_loop']) > 0 else "Nothing is playing"
  }
  
  def __init__(self, server_ip="192.168.1.126", server_port=9000, playername_cleanup_func=None):
    """
    Args:
      server_ip: string,
      server_port: int,
      playername_cleanup_func: (string) -> string
        for tidying up the player names got from the squeeze server
    """
    self.base_url = "http://" + server_ip + ":" + str(server_port)
    self.end_point_url = self.base_url + "/jsonrpc.js"
    self.player_macs = self._populate_player_macs(playername_cleanup_func)
    self._custom_commands = {}
  
  @_cache_player
  def simple_command(self, details):
    """Sends a simple squeezebox commands
    
    Sends one of the fixed commands to the specified squeezebox

    Args:
      details: {"player": string, "command": string}
         - player is the player's name
         - command is one of commands.keys()
    """
    if "player" not in details:
      raise Exception("Player not specified")
    elif "command" not in details:
      raise Exception("Command not specified")

    if details['command'] not in self.commands:
      raise Exception("command must be one of: " + str(self.commands.keys()))
    if details['player'] not in self.player_macs:
      raise Exception("player must be one of: " + ", ".join(self.player_macs.keys()))

    self._make_request(self.player_macs[details['player']], self.commands[details['command']])

  @_cache_player
  def search_and_play(self, details):
    """Plays the specified music
    
    Searches for the specified music and loads it on the specified squeezebox

    Args:
      details: {"player": string, "term": string, "type": string}
        - term is the string to search for
        - type is the search mode: one of search_types.keys()
    """
    if "player" not in details:
      raise Exception("Player not specified")
    elif "term" not in details:
      raise Exception("Search term not specified")
    elif "type" not in details:
      raise Exception("Search type not specified")

    if details['player'] not in self.player_macs:
      raise Exception("player must be one of: " + ", ".join(self.player_macs.keys()))
    if details['term'] == "":
      raise UserException("Search term cannot be empty")
      
    if details['type'] == '$type':
      details['type'] = self.default_search_type
    elif details['type'] not in self.search_types:
      raise Exception("Search type must be one of: " + str(self.search_types.keys()))
      
    result = self._make_request(self.player_macs[details['player']], ["search", 0, 1, "term:" + details["term"]])["result"]

    type = self.search_types[details['type']]
    if type+'s_loop' not in result or len(result[type+'s_loop']) < 1:
      raise UserException("No " + type + " matching: " + details["term"])

    entity = result[type+'s_loop'][0]
    title = entity[type]
    entity_id = entity[type+'_id']
    entity_id_type = 'artist_id:' if details['type'] == "ARTIST" else type+"_id:"
    self._make_request(self.player_macs[details['player']], ["playlistcontrol", "cmd:load", entity_id_type + str(entity_id)])
    return "Playing %s"%title

  @_cache_player
  def spotify_search_and_play(self, details):
    """Plays the specified music on spotify
    
    Searches for the specified music on spotify and loads it on the specified squeezebox

    Args:
      details: {"player": string, "term": string, "type": string}
        - term is the string to search for
        - type is the search mode: one of search_types.keys()
    """
    if "player" not in details:
      raise Exception("Player not specified")
    elif "term" not in details:
      raise Exception("Search term not specified")
    elif "type" not in details:
      raise Exception("Search type not specified")

    if details['player'] not in self.player_macs:
      raise Exception("player must be one of: " + ", ".join(self.player_macs.keys()))
    if details['term'] == "":
      raise UserException("Search term cannot be empty")
      
    if details['type'] == '$type':
      details['type'] = self.default_search_type
    elif details['type'] not in self.search_types:
      raise Exception("Search type must be one of: " + str(self.search_types.keys()))
      
    search_type_num = {
      "SONG": ".2",
      "ALBUM": ".1",
      "ARTIST": ".0"
    }
      
    item_id = "8_" + details["term"] + search_type_num[details['type']]
    command = ["spotify","items","0","1", "item_id:" + item_id, "menu:spotify"]
    result = self._make_request(self.player_macs[details['player']], command)["result"]
    if result["count"] == 0:
      raise UserException("No " + type + " matching: " + details["term"] + "on spotify")
    
    song = result["item_loop"][0]
    uri = song["actions"]["play"]["params"]["uri"]
    title = song["text"]
    
    self._make_request(self.player_macs[details['player']], ["spotifyplcmd", "uri:" + uri, "cmd:load"])
    return "Playing %s"%title
    

  @_cache_player
  def set_volume(self, details):
    """Sets volume at specified level
    
    Sets the volume of the specified squeezebox at the specified level

    Args:
      details: {"player": string, "percent": string}
        - percent is 0 to 100
    """
    if "player" not in details:
      raise Exception("Player not specified")
    elif "percent" not in details:
      raise Exception("Percentage not specified")
    
    if details['player'] not in self.player_macs:
      raise Exception("player must be one of: " + ", ".join(self.player_macs.keys()))
    
    if type(details['percent']) == int:
      percent = details['percent']
    else:
      try:
        percent = int(details['percent'])
      except:
        raise Exception("Percentage must be a integer")
        
    if percent < 0 or percent > 100:
      raise Exception("Percentage must be a integer")
      
    self._make_request(self.player_macs[details['player']], ["mixer","volume",str(percent)])

  @_cache_player
  def send_music(self, details):
    """Sends music from one squeezebox to another
    
    Sends whatever is playing on the source to the destination squeezebox

    Args:
      details: {"player": string, "other": string, "direction": string}
         - direction is either TO or FROM
    """
    if "player" not in details:
      raise Exception("Player not specified")
    if "other" not in details:
      raise Exception("Other player not specified")
    elif "direction" not in details:
      raise Exception("Direction not specified")
    
    if details['player'] not in self.player_macs:
      raise Exception("player must be one of: " + ", ".join(self.player_macs.keys()))
    if details['other'] not in self.player_macs:
      raise Exception("other player must be one of: " + str(self.player_macs.keys()))
    
    if details['direction'] == 'TO':
      source = self.player_macs[details['player']]
      dest = self.player_macs[details['other']]
    elif details['direction'] == 'FROM':
      source = self.player_macs[details['other']]
      dest = self.player_macs[details['player']]
    else:
      raise Exception('direction must be either "from" or "to".')
      
    self._make_request(self.player_macs[details['player']], ["switchplayer","from:" + source,"to:" + dest])
   
  @_cache_player
  def sync_player(self, details):
    """Sends music from one squeezebox to another
    
    Sends whatever is playing on the source to the destination squeezebox

    Args:
      details: {"player": string, "other": string}
    """
    if "player" not in details:
      raise Exception("Player not specified")
    if "other" not in details:
      raise Exception("Other player not specified")
     
    if details['player'] not in self.player_macs:
      raise Exception("player must be one of: " + ", ".join(self.player_macs.keys()))
    if details['other'] not in self.player_macs:
      raise Exception("other player must be one of: " + str(self.player_macs.keys()))
    
    slave = self.player_macs[details['player']]
    master = self.player_macs[details['other']]
      
    self._make_request(master, ["sync",slave])
    self._make_request(slave, self.commands["POWER ON"])
    self._make_request(master, self.commands["POWER ON"])
   
  def add_custom_command(self, name, func, cached=True):
    """Add a named custom command 
    
    Args:
      name: string
      func: (helper_obj, details) -> Unit
        helper_obj: {
          "make_request": func,
          "requests": library object,
          "base_url": string,
          "player_lookup": dict[string] -> string
        }
        details: custom
      cached: boolean
        should the player field be cached
    """
    if cached:
      func = _cache_player_custom(self, func)
    self._custom_commands[name] = func
    
  def custom_command(self, name, details=None):
    """Run named custom command
    
    Args:
      name: string
      details - passed to custom command
    """  
    if name not in self._custom_commands:
      raise Exception("Custom Command not available")
        
    helper = {
      "make_request": partial(self._make_request, self),
      "requests": requests,
      "base_url": self.base_url,
      "player_lookup": self.player_macs
    }
    
    if details == None:
      self._custom_commands[name](helper)
    else:
      self._custom_commands[name](helper, details)
    
    
  @_cache_player
  def simple_query(self, details):
    """Performs a simple query on a squeezebox 
    
    Performs one of the fixed queries on the specified squeezebox

    Args:
      details: {"player": string, "query": string}
         - query is one of queries.keys()
    """
    if "player" not in details:
      raise Exception("Player not specified")
    elif "query" not in details:
      raise Exception("Query not specified")

    if details['query'] not in self.queries:
      raise Exception("Query must be one of: " + str(self.queries.keys()))
    if details['player'] not in self.player_macs:
      raise Exception("player must be one of: " + ", ".join(self.player_macs.keys()))

    player_info = self._get_player_info(self.player_macs[details['player']])
    
    return self.queries[details['query']](player_info)
    

  def _populate_player_macs(self, playername_cleanup=None):
    player_macs = {}
    count = int(self._make_request('-', ["player","count", "?"])['result']['_count'])
    for player in self._make_request('-', ["players","0", count])['result']['players_loop']:
      name = player['name']
      if playername_cleanup != None:
        name = playername_cleanup(name)
      player_macs[name] = player['playerid']
    return player_macs
      
  def _get_player_info(self, player):
    return self._make_request(player, ["status","-"])["result"]
    
  def _make_request(self, player, command):
    payload = {'method': 'slim.request', 'params': [player, command]}
    req = requests.post(self.end_point_url, json=payload)
    return json.loads(req.content.decode("utf-8"))