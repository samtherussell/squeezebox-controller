# Squeezebox Controller

A python interface for controlling logitech squeezeboxes via the squeezebox server.

The commands are sent over the JSON RPC interface to the local squeeze server.

For an explaination of the format of each command see [here](https://gist.github.com/jackoson/335bf9ba75363bd167d2470b8689d9f2)

How to use:

```python
from squeezebox_controller import SqueezeBoxController

controller = SqueezeBoxController("192.168.1.100", 9000)

params = {
  "player": "Lounge",
  "command": "PLAY"
}
controller.simple_command(params)
```