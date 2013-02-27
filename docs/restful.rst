RESTful interface
=================

Documentation on the Sphinx httpdomain extension is `here <http://pythonhosted.org/sphinxcontrib-httpdomain/>`_ and in the README `here <https://github.com/deceze/Sphinx-HTTP-domain>`_.

Some examples pulled from the docs:

.. http:method:: GET /api/foo/bar/{id}/{slug}

   :arg id: An id
   :arg slug: A slug

   Retrieve list of foobars matching given id.

.. http:method:: GET /api/foo/bar/?id&slug

   :param id: An id
   :optparam slug: A slug

   Search for a list of foobars matching given id.

.. http:method:: GET /api/foo/bar/{id}/?slug

   :arg integer id: An id
   :optparam string slug: A slug

   Search for a list of foobars matching given id.

.. http:method:: POST /api/foo/bar/

   :param string slug: A slug
   :response 201: A foobar was created successfully.
   :response 400:

   Create a foobar.

.. http:method:: GET /api/
   :label-name: get-root
   :title: API root

The :http:method:`get-root` contains all of the API.

.. http:response:: Foobar object

A :http:response:`foobar-object` is returned when you foo the bar.