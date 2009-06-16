#!/usr/bin/env python
# -*- coding: utf-8 -*-

from sqlalchemy import *
from sqlalchemy.util import *
from sqlalchemy.exc import *

from migrate.changeset import *

from test import fixture


class CommonTestConstraint(fixture.DB):
    """helper functions to test constraints.
    
    we just create a fresh new table and make sure everything is
    as required.
    """

    def _setup(self, url):
        super(CommonTestConstraint, self)._setup(url)
        self._create_table()

    def _teardown(self):
        if hasattr(self, 'table') and self.engine.has_table(self.table.name):
            self.table.drop()
        super(CommonTestConstraint, self)._teardown()

    def _create_table(self):
        self._connect(self.url)
        self.meta = MetaData(self.engine)
        self.tablename = 'mytable'
        self.table = Table(self.tablename, self.meta,
            Column('id', Integer, unique=True),
            Column('fkey', Integer),
            mysql_engine='InnoDB')
        if self.engine.has_table(self.table.name):
            self.table.drop()
        self.table.create()

        # make sure we start at zero
        self.assertEquals(len(self.table.primary_key), 0)
        self.assert_(isinstance(self.table.primary_key,
            schema.PrimaryKeyConstraint), self.table.primary_key.__class__)


class TestConstraint(CommonTestConstraint):
    level = fixture.DB.CONNECT

    def _define_pk(self, *cols):
        # Add a pk by creating a PK constraint
        pk = PrimaryKeyConstraint(table=self.table, *cols)
        self.assertEquals(list(pk.columns), list(cols))
        if self.url.startswith('oracle'):
            # Can't drop Oracle PKs without an explicit name
            pk.name = 'fgsfds'
        pk.create()
        self.refresh_table()
        if not self.url.startswith('sqlite'):
            self.assertEquals(list(self.table.primary_key), list(cols))

        # Drop the PK constraint
        if not self.url.startswith('oracle'):
            # Apparently Oracle PK names aren't introspected
            pk.name = self.table.primary_key.name
        pk.drop()
        self.refresh_table()
        self.assertEquals(len(self.table.primary_key), 0)
        self.assert_(isinstance(self.table.primary_key, schema.PrimaryKeyConstraint))
        return pk

    @fixture.usedb(not_supported='sqlite')
    def test_define_fk(self):
        """FK constraints can be defined, created, and dropped"""
        # FK target must be unique
        pk = PrimaryKeyConstraint(self.table.c.id, table=self.table, name="pkid")
        pk.create()

        # Add a FK by creating a FK constraint
        self.assertEquals(self.table.c.fkey.foreign_keys._list, [])
        fk = ForeignKeyConstraint([self.table.c.fkey], [self.table.c.id], name="fk_id_fkey")
        self.assert_(self.table.c.fkey.foreign_keys._list is not [])
        self.assertEquals(list(fk.columns), [self.table.c.fkey])
        self.assertEquals([e.column for e in fk.elements], [self.table.c.id])
        self.assertEquals(list(fk.referenced), [self.table.c.id])

        if self.url.startswith('mysql'):
            # MySQL FKs need an index
            index = Index('index_name', self.table.c.fkey)
            index.create()
        fk.create()
        self.refresh_table()
        self.assert_(self.table.c.fkey.foreign_keys._list is not [])

        fk.drop()
        self.refresh_table()
        self.assertEquals(self.table.c.fkey.foreign_keys._list, [])

    @fixture.usedb()
    def test_define_pk(self):
        """PK constraints can be defined, created, and dropped"""
        self._define_pk(self.table.c.id)

    @fixture.usedb()
    def test_define_pk_multi(self):
        """Multicolumn PK constraints can be defined, created, and dropped"""
        #self.engine.echo=True
        self._define_pk(self.table.c.id, self.table.c.fkey)

    @fixture.usedb()
    def test_drop_cascade(self):
        pk = PrimaryKeyConstraint('id', table=self.table, name="id_pkey")
        pk.create()
        self.refresh_table()

        # Drop the PK constraint forcing cascade
        pk.drop(cascade=True)


class TestAutoname(CommonTestConstraint):
    """Every method tests for a type of constraint wether it can autoname
    itself and if you can pass object instance and names to classes.
    """
    level = fixture.DB.CONNECT

    @fixture.usedb(not_supported='oracle')
    def test_autoname_pk(self):
        """PrimaryKeyConstraints can guess their name if None is given"""
        # Don't supply a name; it should create one
        cons = PrimaryKeyConstraint(self.table.c.id)
        cons.create()
        self.refresh_table()
        if not self.url.startswith('sqlite'):
            # TODO: test for index for sqlite
            self.assertEquals(list(cons.columns), list(self.table.primary_key))

        # Remove the name, drop the constraint; it should succeed
        cons.name = None
        cons.drop()
        self.refresh_table()
        self.assertEquals(list(), list(self.table.primary_key))

        # test string names
        cons = PrimaryKeyConstraint('id', table=self.table)
        cons.create()
        self.refresh_table()
        if not self.url.startswith('sqlite'):
            # TODO: test for index for sqlite
            self.assertEquals(list(cons.columns), list(self.table.primary_key))
        cons.name = None
        cons.drop()

    @fixture.usedb(not_supported=['oracle', 'sqlite'])
    def test_autoname_fk(self):
        """ForeignKeyConstraints can guess their name if None is given"""
        cons = ForeignKeyConstraint([self.table.c.fkey], [self.table.c.id])
        if self.url.startswith('mysql'):
            # MySQL FKs need an index
            index = Index('index_name', self.table.c.fkey)
            index.create()
        cons.create()
        self.refresh_table()
        self.table.c.fkey.foreign_keys[0].column is self.table.c.id

        # Remove the name, drop the constraint; it should succeed
        cons.name = None
        cons.drop()
        self.refresh_table()
        self.assertEquals(self.table.c.fkey.foreign_keys._list, list())

        # test string names
        cons = ForeignKeyConstraint(['fkey'], ['%s.id' % self.tablename], table=self.table)
        if self.url.startswith('mysql'):
            # MySQL FKs need an index
            index = Index('index_name', self.table.c.fkey)
            index.create()
        cons.create()
        self.refresh_table()
        self.table.c.fkey.foreign_keys[0].column is self.table.c.id

        # Remove the name, drop the constraint; it should succeed
        cons.name = None
        cons.drop()

    @fixture.usedb(not_supported=['oracle', 'sqlite'])
    def test_autoname_check(self):
        """CheckConstraints can guess their name if None is given"""
        cons = CheckConstraint('id > 3', columns=[self.table.c.id])
        cons.create()
        self.refresh_table()

    
        self.table.insert(values={'id': 4}).execute()
        try:
            self.table.insert(values={'id': 1}).execute()
        except IntegrityError:
            pass
        else:
            self.fail()

        # Remove the name, drop the constraint; it should succeed
        cons.name = None
        cons.drop()
        self.refresh_table()
        self.table.insert(values={'id': 2}).execute()
        self.table.insert(values={'id': 5}).execute()

    @fixture.usedb(not_supported=['oracle', 'sqlite'])
    def test_autoname_unique(self):
        """UniqueConstraints can guess their name if None is given"""
        cons = UniqueConstraint(self.table.c.fkey)
        cons.create()
        self.refresh_table()

    
        self.table.insert(values={'fkey': 4}).execute()
        try:
            self.table.insert(values={'fkey': 4}).execute()
        except IntegrityError:
            pass
        else:
            self.fail()

        # Remove the name, drop the constraint; it should succeed
        cons.name = None
        cons.drop()
        self.refresh_table()
        self.table.insert(values={'fkey': 4}).execute()
        self.table.insert(values={'fkey': 4}).execute()
