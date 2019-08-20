# Building

You'll need wxpython. Nominally you can get it through pip by just running `pip install --user wxpython`,
but you may need some dependencies first. The full list is available [here](https://github.com/wxWidgets/Phoenix/blob/master/README.rst#prerequisites).

On my Fedora system, [this blog post](https://blog.wizardsoftheweb.pro/installing-wxpython-on-fedora/)
had a list of all the needed packages, except for `python3-pathlib2`. The wxpython installer will probably give you
the names of any missing dependencies it encounters.

There's also a **pipenv** included, which should install the dependencies with just `pipenv install --ignore-pipfile`.
That said you will probably still need the build dependencies for wxpython installed systemwide.

Note that installing wxpython like this is SLOW, because it's compiled locally.
On my laptop (Intel i5 5300u) it took about 30 minutes.
