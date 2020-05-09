import math
from collections import deque

"""
_v_weights = {
  "correct": lambda l: 0-math.floor(math.pow(l,1.2)),
  "add": lambda l: math.floor(2*(math.log(l) + 1)),
  "sub": lambda l: math.floor(6*(math.log(l) + 1)),
  "swap": lambda l: math.floor(7*(math.log(l) + 1)),
  "trans": lambda l: math.floor(1*(math.log(l) + 1))
}
"""

_v_weights = {'trans': [1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4], 'correct': [-1, -2, -3, -5, -6, -8, -10, -12, -13, -15, -17, -19, -21, -23, -25, -27, -29, -32, -34, -36, -38, -40, -43, -45, -47, -49, -52, -54, -56], 'add': [2, 3, 4, 4, 5, 5, 5, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8], 'sub': [6, 10, 12, 14, 15, 16, 17, 18, 19, 19, 20, 20, 21, 21, 22, 22, 22, 23, 23, 23, 24, 24, 24, 25, 25, 25, 25, 25, 26], 'swap': [7, 11, 14, 16, 18, 19, 20, 21, 22, 23, 23, 24, 24, 25, 25, 26, 26, 27, 27, 27, 28, 28, 28, 29, 29, 29, 30, 30, 30]}

def dist(a, b):
  """Calculates similarity heuristic

  Based on edit distance with extras and shortcurts to speed up.

  IS reflexive
  NOT symetric or transistive
  DOESN'T satisfy triangle property
  ISN'T always > 0

  strings get rewards for identical sequences (polynomial with length)
  strings get penalities (logarithmic with length) for having to add, subtract or swap character blocks to match target.
  strings also get (smaller) penalities (logarithmic with length) for transposing blocks to match target.
  """
  mem = {}
  def d(s,a, b):
    if (a,b) in mem:
      return mem[(a,b)]
    elif len(a) == 0:
      mem[(a,b)] = len(b)
      return len(b)
    elif len(b) == 0:
      mem[(a,b)] = len(a)
      return len(a)
    else:
      options = []
      minlen = min(len(a), len(b)) + 1
      for i in reversed(range(1, minlen, 3)):
        if a[:i] == b[:i]:
          options = options + [
            _v_weights["correct"][i] + d(s+1, a[i:], b[i:]),
            _v_weights["add"][i] + d(s+1, a, b[i:]),
            _v_weights["sub"][i] + d(s+1, a[i:], b)
          ]
          break
        else:
          options = options + [
            _v_weights["swap"][i] + d(s+1, a[i:], b[i:]),
            _v_weights["add"][i] + d(s+1, a, b[i:]),
            _v_weights["sub"][i] + d(s+1, a[i:], b)
          ]

      if len(a) > 1 and len(b) > 1:
        for i in range(5,minlen, 2):
          for j in range(i, minlen-i):
            if a[:i] == b[j:j+i]:
              options.append(_v_weights["trans"][i] + d(s+1, a[i:], b[:j] + b[j+i:]))
            if a[j:j+i] == b[:i]:
              options.append(_v_weights["trans"][i] + d(s+1, a[:j] + a[j+i:], b[i:]))

      v = min(options)
      mem[(a,b)] = v
      return v
  return d(0,a,b)

def try_match(input, options, threshold=5):
  input = input.lower()
  scores = []
  for key in options:
    option = options[key]
    scores.append((key, dist(input, key.lower())))
    if type(option) == dict and "synonyms" in option:
      for regex in option["synonyms"]:
        for text in enumerate_regex(regex.lower()):
          scores.append((key, dist(input, text.lower())))
  print(sorted(scores, key=lambda x: x[1])) 
  best = min(scores, key=lambda x: x[1])
  if best[1] < threshold:
    print(f"return {best}")
    return best[0]
  else:
    print(f"return None")
    return None


def enumerate_regex(regex):
  done = []
  doing = deque([('', regex)])
  while len(doing) > 0:
    x = doing.popleft()
    s,r = x
    start = r.find('(')
    if start == -1:
      done.append(s + r)
      continue

    end = r.find(')', start+1)
    if end == -1:
      raise Exception(f"bad regex: {r}")

    options = r[start+1:end].split('|')
    if end+1 < len(r) and r[end+1] == '?':
      options.append('')
      end += 1

    before = r[:start]
    after = r[end+1:]
    for option in options:
      doing.append((s + before + option, after))

  return done
