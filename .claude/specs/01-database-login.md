
## Overview

Implement a registration and login system with our current database
we also have a next js frontend where UI for login and registration will be present


1. Db connection is already done with postgres


## Database Scheme

A. users

Column      Type        Constraints
id          INTEGER     primary key, auto_increment
name        text        not null
email       text        not null
password    text        not null
created_at  timestamp   default datetime('now')


## Routes

1. For Login : /login
2. For Registration : /register


## Rules For Implementation

1. password must be hashed before saving into the database
2. Dates must follow YYYY-MM-DD format consistently



## Error Handling

1. duplicate email not allowed
2. show errors and wanrning consistently wherever requried


## Definition of Done

1. User must be able to register
2. User must be able to login