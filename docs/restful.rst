RESTful interface
=================

Documentation on the Sphinx httpdomain extension is `here <http://pythonhosted.org/sphinxcontrib-httpdomain/>`_ and in the README `here <https://github.com/deceze/Sphinx-HTTP-domain>`_.

Some examples pulled from the docs:

.. http:method:: GET /accounts

   Retrieve a list of all available accounts.

.. http:method:: GET /accounts/{account_name}

   :arg account_name: Name of the account
   :response 404: Account not found

   Retrieve information of a specified account (mostly authentication information).

.. http:method:: GET /accounts/{account_name}/machines

   :arg account_name: Name of the account
   :response 404: Account not found

   Retrieve a list of all available machines in a specified account.

.. http:method:: GET /accounts/{account_name}/machines/{machine_name}

   :arg account_name: Name of the account
   :arg machine_name: Name of the machine
   :response 404: Account or machine not found

   Retrieve information about a specified machine.



.. http:method:: POST /accounts/{account_name}/machines/{machine_name}/instance

   **Example request**:
   
   .. sourcecode:: http
   
       POST /accounts/my-account/machines/my-machine/instance HTTP/1.1
   
   **Example response**:
   
   .. sourcecode:: http
   
       HTTP/1.1 202 OK
       Content-Type: application/json; charset=UTF-8
       
       {"output":
          {"launch_id": "L-abcdefg-0000000000000000"}
       }
       
   :arg account_name: Name of the account
   :arg machine_name: Name of the machine
   :response 202: Instance successfully enqueued and is launching
   :response 400: Bad authentication type or value
   :response 404: Account or machine not found
   :response 500: Server error

   Launch an instance from the snapshot of a specified machine (TODO: json body).

