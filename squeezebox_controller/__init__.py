import requests
import json
from functools import wraps, partial

from squeezebox_controller.string_distance import dist

class UserException(Exception):
  pass

def _cache_player(f):
  @wraps(f)
  def cached_f(self, details, *args):
    if (not self.cached_player == None) and ("player" not in details or details["player"] == ""):
      details["player"] = self.cached_player
    else:
      self.cached_player = details['player']
    return f(self, details, *args)
  return cached_f
  
def _cache_player_custom(self, f):
  @wraps(f)
  def cached_f(helper, details, *args):
    if (not self.cached_player == None) and ("player" not in details or details["player"] == ""):
      details["player"] = self.cached_player
    else:
      self.cached_player = details['player']
    return f(helper, details, *args)
  return cached_f

def _needs_player(field):
  def dec(f):
    @wraps(f)
    def needs_player_f(self, details, *args):
      if field not in details:
        raise Exception("%s not specified"%field)
      if details[field] not in self.player_macs:
        raise Exception("%s must be one of: %s"%(field, ", ".join(self.player_macs.keys())))
      return f(self, details, *args)
    return needs_player_f
  return dec

commands = {
  "PLAY": ["play"],
  "PAUSE": ["pause"],
  "POWER ON": ["power", "1"],
  "POWER OFF": ["power", "0"],
  "VOLUME UP": ["mixer","volume","+20"],
  "VOLUME DOWN": ["mixer","volume","-20"],
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
  "REPEAT PLAYLIST": ["playlist","repeat",2],
  "MUTE": ["mixer","volume","0"]
} 
 
search_types = {
  "SONG": {"print": "song", "local_search":"tracks", "local_loop":"titles_loop", "local_name": "title", "local_play": "track_id"},
  "ALBUM": {"print": "album", "local_search":"albums", "local_loop":"albums_loop", "local_name": "album", "local_play": "album_id"},
  "ARTIST": {"print": "artist", "local_search":"artists", "local_loop":"artists_loop", "local_name": "artist", "local_play": "artist_id"},
  "GENRE": {"print": "genre", "local_search":"genres", "local_loop":"genres_loop", "local_name": "genre", "local_play": "genre_id"},
  "PLAYLIST": {"print": "playlist", "local_search":"playlists", "local_loop":"playlists_loop", "local_name": "playlist", "local_play": "playlist_id"},
}

queries = {
  "RAW": lambda info: info,
  "VOLUME": lambda info: "The volume is at %d percent"%(info['mixer volume']),
  "NOW PLAYING": lambda info: info['playlist_loop'][0]['title'] + ' by ' + info['playlist_loop'][0]['artist'] \
                      if 'artist' in info['playlist_loop'][0] else info['playlist_loop'][0]['title'] \
                      if 'playlist_loop' in info and len(info['playlist_loop']) > 0 else "Nothing is playing"
}
 
class SqueezeBoxController:

  cached_player = None
  
  def __init__(self, server_ip, server_port=9000, playername_cleanup_func=None, default_player = None, request_lib=requests):
    """
    Args:
      server_ip: ``string``,
      server_port: ``int``,
      playername_cleanup_func: ``(string) -> string``
        for tidying up the player names got from the squeeze server
    """
    self.base_url = "http://" + server_ip + ":" + str(server_port)
    self.end_point_url = self.base_url + "/jsonrpc.js"
    self.request_lib = request_lib
    self.player_macs = self._populate_player_macs(playername_cleanup_func)
    self._custom_commands = {}
    self.cached_player = default_player

  @_cache_player
  @_needs_player("player")
  def simple_command(self, details):
    """Sends a simple squeezebox commands
    
    Sends one of the fixed commands to the specified squeezebox

    Args:
      details: {"player": ``string``, "command": ``string``}
         - player is the player's name
         - command is one of ``commands.keys()``
    """
    if "command" not in details:
      raise Exception("Command not specified")

    if details['command'] not in commands:
      raise Exception("command must be one of: " + str(commands.keys()))

    self._make_request(self.player_macs[details['player']], commands[details['command']])

  @_cache_player
  def search_and_play(self, details):
    """Plays the specified music

    Searches for the specified music and loads it on the specified squeezebox

    Args:
      details: {"player": ``string``, "term": ``string``, "type": ``string``}
        - term is the string to search for
        - type is the search mode: one of ``search_types.keys()``
    """
    return "Playing %s"%self._search_and(details, "load")

  @_cache_player
  def search_and_play_next(self, details):
    """Plays the specified music next

    Searches for the specified music and loads it to play next on the specified squeezebox.

    Args:
      details: {"player": ``string``, "term": ``string``, "type": ``string``}
        - term is the string to search for
        - type is the search mode: one of ``search_types.keys()``
    """
    return "Playing %s next"%self._search_and(details, "insert")

  @_cache_player
  def search_and_play_end(self, details):
    """Plays the specified music at end.

    Searches for the specified music and loads it on to the end of the specified squeezebox's playlist.

    Args:
      details: {"player": ``string``, "term": ``string``, "type": ``string``}
        - term is the string to search for
        - type is the search mode: one of ``search_types.keys()``
    """
    return "Queuing %s"%self._search_and(details, "add")

  @_needs_player("player")
  def _search_and(self, details, command):
    if "term" not in details:
      raise Exception("Search term not specified")
    elif "type" not in details:
      raise Exception("Search type not specified")

    if details['term'] == "":
      raise UserException("Search term cannot be empty")
      
    if details['type'] == "":
      specified_search_types = search_types.keys()
    elif details['type'] not in search_types:
      raise Exception("Search type must be one of: " + str(search_types.keys()))
    else:
      specified_search_types = [details['type']]

    results = []
    for type_k in specified_search_types:
      type = search_types[type_k]
      result = self._make_request(self.player_macs[details['player']], [type["local_search"], 0, 10, "search:" + details["term"]])["result"]

      if type['local_loop'] in result:
        results = results + [ (r, type_k) for r in result[type['local_loop']] ]

    if len(results) < 1:
      raise UserException("Nothing matching: " + details["term"])

    results.sort(key=lambda x: dist(x[0][search_types[x[1]]['local_name']], details["term"]))
    
    entity,type_k = results[0]
    type = search_types[type_k]
    name = entity[type['local_name']]
    entity_id = entity['id']
    self._make_request(self.player_macs[details['player']], ["playlistcontrol", "cmd:"+command, type['local_play'] + ":" + str(entity_id)])
    return name

  @_cache_player
  @_needs_player("player")
  def set_volume(self, details):
    """Sets volume at specified level
    
    Sets the volume of the specified squeezebox at the specified level

    Args:
      details: {"player": ``string``, "percent": ``string``}
        - percent is 0 to 100
    """
    if "percent" not in details:
      raise Exception("Percentage not specified")
    
    if type(details['percent']) == int:
      percent = details['percent']
    else:
      try:
        percent = int(details['percent'])
      except:
        raise Exception("Percentage must be a integer")
        
    if percent < 0 or percent > 100:
      raise Exception("Percentage must be between 0 and 100")
      
    self._make_request(self.player_macs[details['player']], ["mixer","volume",str(percent)])

  @_cache_player
  @_needs_player("player")
  def sleep_in(self, details):
    """Sleeps the player after a delay
    
    Sets the specified squeezebox to sleep after the specified time

    Args:
      details: {"player": ``string``, "time": ``string``}
        - time is number of minutes
    """
    if "time" not in details:
      raise Exception("Time not specified")

    if type(details['time']) == int:
      time = details['time']
    else:
      try:
        time = int(details['time'])
      except:
        raise Exception("Time must be a integer")
        
    if time < 0:
      raise Exception("Time must be positive")
      
    self._make_request(self.player_macs[details['player']], ["sleep",str(time*60)])

  @_cache_player
  @_needs_player("player")
  @_needs_player("other")
  def send_music(self, details):
    """Sends music from one squeezebox to another
    
    Sends whatever is playing on the source to the destination squeezebox

    Args:
      details: {"player": ``string``, "other": ``string``, "direction": ``string``}
         - direction is either TO or FROM
    """
    if "direction" not in details:
      raise Exception("Direction not specified")

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
  @_needs_player("player")
  @_needs_player("other")
  def sync_player(self, details):
    """Sends music from one squeezebox to another
    
    Sends whatever is playing on the source to the destination squeezebox

    Args:
      details: {"player": ``string``, "other": ``string``}
    """
    slave = self.player_macs[details['player']]
    master = self.player_macs[details['other']]
      
    self._make_request(master, ["sync",slave])
    self._make_request(slave, commands["POWER ON"])
    self._make_request(master, commands["POWER ON"])
   
  def add_custom_command(self, name, func, cached=True):
    """Performs a simple query on a squeezebox 
    
    Performs one of the fixed queries on the specified squeezebox

    Args:
      name: ``string``,
      func: ``(helper_obj, details) -> Unit``,
      cached: ``boolean`` - should the player field be cached
      
    helper_obj:
      Is an dictionary with the following contents...
      "make_request": ``(mac: string, command: [string]) -> Unit``,
      "get_player_info": ``(mac: string) -> JSON``,
      "requests": library object,
      "base_url": ``string``,
      "player_lookup": ``dict[string] -> string``
      
    details: [optional] the parameter object to pass to the called custom function.
    """
    if cached:
      func = _cache_player_custom(self, func)
    self._custom_commands[name] = func
    
  def custom_command(self, name, details=None):
    """Run named custom command
    
    Args:
      name: ``string``
      details - passed to custom command
    """  
    if name not in self._custom_commands:
      raise Exception("Custom Command not available")
        
    helper = {
      "make_request": partial(self._make_request),
      "get_player_info": partial(self._get_player_info),
      "requests": self.request_lib,
      "base_url": self.base_url,
      "player_lookup": self.player_macs
    }
    
    if details == None:
      return self._custom_commands[name](helper)
    else:
      return self._custom_commands[name](helper, details)
    
  @_cache_player
  @_needs_player("player")
  def simple_query(self, details):
    """Performs a simple query on a squeezebox 
    
    Performs one of the fixed queries on the specified squeezebox

    Args:
      details: {"player": ``string``, "query": ``string``}
         - query is one of ``queries.keys()``
    """
    if "query" not in details:
      raise Exception("Query not specified")

    if details['query'] not in queries:
      raise Exception("Query must be one of: " + str(queries.keys()))

    player_info = self._get_player_info(self.player_macs[details['player']])
    
    return queries[details['query']](player_info)
    

  def _populate_player_macs(self, playername_cleanup=None):
    player_macs = {}
    count = int(self._make_request('-', ["player","count", "?"])['result']['_count'])
    for player in self._make_request('-', ["players","0", count])['result']['players_loop']:
      name = player['name']
      assert not name == "ALL"
      if playername_cleanup != None:
        name = playername_cleanup(name)
      player_macs[name] = player['playerid']
    player_macs["ALL"] = list(player_macs.values())
    return player_macs
      
  def _get_player_info(self, player):
    return self._make_request(player, ["status","-"])["result"]
    
  def _make_request(self, player, command):
    def handler(p):
      payload = {'method': 'slim.request', 'params': [p, command]}
      req = self.request_lib.post(self.end_point_url, json=payload)
      return json.loads(req.content.decode("utf-8"))

    if type(player) == list:
      return [handler(p) for p in player]
    elif type(player) == str:
      return handler(player)
    else:
      raise Exception("Player must be a MAC string or list of MAC strings")
    
    