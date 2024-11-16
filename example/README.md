# Federation example

This set of directories allows you to set up 2 federations, together
containing two RPs, an OP, two intermediates and 2 trust anchors.

The trust anchors controls two federations (SEID and SWAMID).

The two organizations (UMU&LU) both belong to both federations.

UMU has one subordinate, an OP.
LU has two subordinates; one RP that does automatic registration and another
that does explicit registration.

            +-----------------+         +-----------------+
            |     SEID        |:7001    |     SWAMID      |:7002
            | Trust Anchor    |         | Trust Anchor    |
            +--------+--------+         +--------+--------+
                     |                           |
     +---------------|---------------------------+
     |               |                           |
     |        +------+--------------------+      |
     |        |                           |      |    
+----+--------+--+                    +---+------+------+
|     UMU        |:6002               |       LU        |:6003
| Organization   |                    |   Organization  |
+-------+--------+                    +---+----------+--+
        |                                 |          |_____________ 
        |                                 |                        |
  +-----+-------+                    +----+--------+         +-----+----------+
  |   OP        |                    |   RP        |         |   RP           |
  | Subordinate |:5000               | Subordinate |:4001    | Subordinate    |:4002
  |             |                    |             |         |                |
  | (UMU OP)    |                    | (Auto Reg)  |         | (Explicit Reg) |
  +-------------+                    +-------------+         +----------------+

# Setting up the test federations

There is a set of information that must be the same in different places in
the setup. For instance must the keys in the trust_roots in a leaf entity
correspond to the keys owned by the trusted anchors.

Subordinates must also be registered with their authorities.

All of this can be accomplished by using the script `setup.py`. 

`setup.py` **MUST** be run before you attempt to start the entities. 

# Testing and verifying the example federation

## Starting/stopping entities

For the commands below to work you are supposed to
stand in the fedservice/example directory.

A simple script for starting/stopping entities:

    ./exec.py start rpa rpe op lu umu seid swamid

This will start all entities in the example federations.


The different entities are:

    RPA
        RP that uses automatic registration
    RPE
        RP that uses explicit registration
    OP
        An OP
    UMU
        An intermediate representing an organization
    LU
        Another intermediate representinng anothe organization
    SEID
        A trust anchor
    SWAMID
        Another trust anchor

Both UMU and LU are members of both federations.

Stopping an entity is as simple as starting it:

    ./exec.py kill RPA

The above command will kill only the RPA entity.

## Displaying an entity's entity statement

For this you can use the `display_entity.py` script:

    ./display_entity.py https://127.0.0.1:5000

Will display the Entity Configuration of the entity that has the provided entity_id.
If the entity is an intermediate or trust anchor, that is has subordinates,
it will also list the subordinates. 
As UMU is the superior of the OP if you do:

    ./display_entity.py https://127.0.0.1:6002

You will get a list of 2 entities: https://127.0.0.1:6002 (UMU)
and https://127.0.0.1:5000 (OP).

## Parsing trust chains.

To do this you use `get_chains.py`

    ../script/get_trust_chains.py -k -t trust_anchors.json https://127.0.0.1:5000

* -k : Don't try to verify the certificate used for TLS
* -t : A JSON file with a list of trust anchors.
* The entity ID of the target

This will list the entity statements of the entities in the collected trust 
chains. Each list will start with the trust anchor and then list the
intermediates and finally the leaf in that order.

If you do:

    ./exec.py start OP UMU LU SWAMID SEID
    ../script/get_trust_chains.py -k -t trust_anchors.json https://127.0.0.1:5000

You will see 2 lists. Each with 3 entities in it.

One can also play around with `get_entity_statement.py`

usage: get_entity_statement.py [-h] [-k] [-t TRUST_ANCHORS_FILE] [-c] [-s SUPERIOR] entity_id

positional arguments:
    entity_id

    options:

    -h, --help            show this help message and exit
    -k, --insecure 
    -t TRUST_ANCHORS_FILE, --trust_anchors_file TRUST_ANCHORS_FILE
    -c
    -s SUPERIOR, --superior SUPERIOR

and an example:

../script/get_subordinate_statement.py -k -c -t trust_anchors_local.json -s https://127.0.0.1:6002 https://127.0.0.1:5000
../script/list_subordinates.py -k -t trust_anchors.json http://127.0.0.1:6002

This will first display the Entity Configuration for https://127.0.0.1:5000
and then the Entity Statement for https://127.0.0.1:5000 as produced by
https://127.0.0.1:6002