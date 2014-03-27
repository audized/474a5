# Overview

Welcome to the exciting world of inconsistencies: where the ordering is 
made up and the local timestamps don't matter!

Messages tend not to arrive in a nice coherent order, so we must account
for that. Since epochal timestamps are of no use to us, every incoming
rating now comes with a vector clock timestamp.

Your goal is twofold: firstly, to keep track of a list of rating messages
since we might not be sure which one is precisely the newest. Secondly,
to take these ratings and determine which of them can be thrown out; 
some of them will eventually be superceded by newer ones (that is to say 
we can get rid of ratings that are strictly older than any existing 
ratings).

The incoming rating now includes an additional field "clock":

```
PUT /rating/maharaja-chai-oolong
{	
	# What the rating for the entity is
	"rating": 5,

	# The clock from the client submitting the rating
	"clock": { "c0": 3, "c1": 2, "c6": 9 }
}
```

The result you send back to the client should now include a list of possible
ratings and their corresponding vector clock timestamps.

```
GET /rating/maharaja-chai-oolong
{
	# The disambiguated final, rating for the entity
	# This is the arithmetic mean of all the choices
	# Three or more decimal places are acceptable.
	"rating": 3.333,
	
	# All the ratings whose ordering is incomparable 
	"choices": [ 4, 5, 1 ],

	# The clocks associated with the above choices
	"clocks": [ { "c0": 22 }, { "c5": 40 }, { "c3": 91, "c5": 37 }  ]
}

## Request / Response Examples

Here are examples of the different cases you must handle:

### Simple (no prior value)
PUT /rating/tea-x <- { "rating": 5, "clock": { "c0": 1 } }
GET /rating/tea-x -> { "rating": 5, "choices": [ 5 ], "clocks": [ { "c0": 1 } ] }

### More Recent Data
GET /rating/tea-x -> { "rating": 5, "choices": [ 5 ], "clocks": [ { "c0": 1 } ] }
PUT /rating/tea-x <- { "rating": 1, "clock": { "c0": 3 } }
GET /rating/tea-x -> { "rating": 1, "choices": [ 1 ], "clocks": [ { "c0": 3 } ] }

### Stale Data (note that it is ignored)
GET /rating/tea-x -> { "rating": 5, "choices": [ 5 ], "clocks": [ { "c0": 5 } ] }
PUT /rating/tea-x <- { "rating": 2, "clock": { "c0": 1 } }
GET /rating/tea-x -> { "rating": 5, "choices": [ 5 ], "clocks": [ { "c0": 5 } ] }

### Incomparable Data (accumulated in lists of choices and clocks)
GET /rating/tea-x -> { "rating": 5, "choices": [ 5 ], "clocks": [ { "c0": 5 } ] }
PUT /rating/tea-x <- { "rating": 2, "clock": { "c1": 3 } }
GET /rating/tea-x -> { "rating": 3.5, "choices": [ 5, 2 ], "clocks": [ { "c0": 5 }, { "c1": 3 } ] }

### Coalescable Data (more recent than both values, so it overrides both)
GET /rating/tea-x -> { "rating": 3.5, "choices": [ 5, 2 ], "clocks": [ { "c0": 5 }, { "c1": 3 } ] }
PUT /rating/tea-x <- { "rating": 3, "clock": { "c0": 7, "c1": 10 } }
GET /rating/tea-x -> { "rating": 3, "choices": [ 3 ], "clocks": [ { "c0": 7, "c1": 10 } ] }

## Vector Clock Examples

We have provided David Drysdale's implementation of vector clocks in the file vectorclock.py
You only need to call the functions. Here are examples of the functions you might use.

Hint: you will have to develop an algorithm similar to VectorClock.converge(). You will
not be able to use the function itself, though. (Why?)

### Creating a vector clock

```python
vc1 = VectorClock().update('c0', 5) # Client 'c0' at time 5
vc2 = VectorClock.fromDict({'c0':5}) # Equivalent (create from a dictionary)
vc1 == vc2
```

### Comparable Clocks

```python
v1,v2 = VectorClock().update('c0', 1), VectorClock().update('c0', 4)
v2 > v1 # True
v1 < v2 # True
v3 = VectorClock.coalesce([v1,v2]) # A list containing a new clock object, equal to v2.
v1 <  v3[0] # True
v2 <  v3[0] # False
v2 <= v3[0] # True
v2 == v3[0] # True
```

### Incomparable Clocks

```python
v1,v2 = VectorClock.fromDict({ 'c0': 12 }), VectorClock.fromDict({ 'c1': 6 })
v2 > v1 # False!
v1 > v2 # False!
vcl = VectorClock.coalesce([v1,v2]) # A list containing two new clocks, copies of v1 and v2
v1 in vcl # True
v2 in vcl # True
```

### Forcing Convergence of Incomparable Clocks

```python
v1,v2 = VectorClock().update('c0', 10), VectorClock().update('c3', 20)
v1 <= v2 # False
v2 <= v1 # False
vconv = VectorClock.converge([v1,v2]) # A single clock that is >= all in the list
v1 <= vconv # True
v2 <= vconv # True
```
