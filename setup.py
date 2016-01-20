"""
Flask-SimpleValidator
-------------

@TODO
"""

from setuptools import setup


setup(
    name='Flask-SimpleValidator',
    version='0.1',
    url='http://example.com/flask-sqlite3/',
    license='BSD',
    author='Dnox',
    author_email='roflik@mail.ru',
    description='Simple validation of income args',
    long_description=__doc__,
    py_modules=['validator'],
    # if you would be using a package instead use packages instead
    # of py_modules:
    # packages=['flask_sqlite3'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask',
        'colander'
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
