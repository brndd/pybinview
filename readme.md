# Building

You'll need wxpython. Nominally you can get it through pip by just running `pip install --user wxpython`,
but you may need some dependencies first. The full list is available [here](https://github.com/wxWidgets/Phoenix/blob/master/README.rst#prerequisites).

You will also need pypubsub, which you can get with `pip install --user pypubsub`.

On my Fedora system, [this blog post](https://blog.wizardsoftheweb.pro/installing-wxpython-on-fedora/)
had a list of all the needed packages, except for `python3-pathlib2`. The wxpython installer will probably give you
the names of any missing dependencies it encounters.

There's also a **pipenv** included, which should install the dependencies with just `pipenv install --ignore-pipfile`.
This is probably the easiest way to get all the dependencies and does not pollute your system or user with packages.
That said you will probably still need the build dependencies for wxpython installed systemwide.

Note that installing wxpython like this is SLOW, because it's compiled locally.
On my laptop (Intel i5 5300u) it took about 30 minutes.

# testdata.dat

Included is a sample binary file to test the program on. It contains 10 structs of the following
format (little-endian):

- A random char (1 byte) value.
- A random short int (2 bytes) value.
- A random int (4 bytes) value.
- A random long int (8 bytes) value.
- A random double-precision floating point (8 bytes) value.
- A null-terminated string containing the text: "The contents of this string don't really matter."

A .csv file containing matching data is provided to compare results.

New testdata can be generated using create_test_data.py.
