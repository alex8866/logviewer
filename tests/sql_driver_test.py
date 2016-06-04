import unittest
import random

from sql_driver import SqlDriver

class SqlDriverTest(unittest.TestCase):
    class FakeSqlDriver(SqlDriver):
        def __init__(self, **kwargs):
            SqlDriver.__init__(self, **kwargs)
            self.query = None
            self.magic = random.randint(1, 1000)

        def select(self, query):
            self.query = query
            return self.magic

    def test_should_execute_query_without_initial_id(self):
        drv = SqlDriverTest.FakeSqlDriver()
        self.assertEqual(drv.magic, drv.prepare_query(None, True, 10))

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs ORDER BY id DESC LIMIT 10", drv.query)

    def test_should_execute_query_with_different_limit(self):
        drv = SqlDriverTest.FakeSqlDriver()
        self.assertEqual(drv.magic, drv.prepare_query(None, True, 1))

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs ORDER BY id DESC LIMIT 1", drv.query)

    def test_should_execute_query_with_an_initial_id(self):
        drv = SqlDriverTest.FakeSqlDriver()
        self.assertEqual(drv.magic, drv.prepare_query(100, True, 10))

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 ORDER BY id DESC LIMIT 10",
            drv.query)

    def test_should_execute_query_in_ascending_order(self):
        drv = SqlDriverTest.FakeSqlDriver()
        self.assertEqual(drv.magic, drv.prepare_query(100, False, 10))

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id > 100 ORDER BY id ASC LIMIT 10",
            drv.query)

    def test_should_execute_query_with_level_filter(self):
        drv = SqlDriverTest.FakeSqlDriver(level=3)
        self.assertEqual(drv.magic, drv.prepare_query(100, True, 10))

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND level_num <= 3 "\
            "ORDER BY id DESC LIMIT 10", drv.query)

    def test_should_execute_query_with_facility_filter(self):
        drv = SqlDriverTest.FakeSqlDriver(facility=5)
        self.assertEqual(drv.magic, drv.prepare_query(100, True, 10))

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND facility_num = 5 "\
            "ORDER BY id DESC LIMIT 10", drv.query)

    def test_should_filter_query_by_one_program(self):
        drv = SqlDriverTest.FakeSqlDriver(program='sshd')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "(program = 'sshd') ORDER BY id DESC LIMIT 10", drv.query)

    def test_should_filter_query_by_multiple_programs(self):
        drv = SqlDriverTest.FakeSqlDriver(program='sshd sudo')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "(program = 'sshd' OR program = 'sudo') ORDER BY id DESC LIMIT 10",
            drv.query)

    def test_should_filter_by_program_stripping_extra_spaces(self):
        drv = SqlDriverTest.FakeSqlDriver(program=' sshd  sudo ')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "(program = 'sshd' OR program = 'sudo') ORDER BY id DESC LIMIT 10",
            drv.query)

    def test_should_filter_program_with_wildcard(self):
        drv = SqlDriverTest.FakeSqlDriver(program='s*')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "(program LIKE 's%') ORDER BY id DESC LIMIT 10", drv.query)

    def test_should_filter_program_with_negative_condition(self):
        drv = SqlDriverTest.FakeSqlDriver(program='!sshd')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "program <> 'sshd' ORDER BY id DESC LIMIT 10", drv.query)

    def test_should_filter_program_with_negative_wildcard_condition(self):
        drv = SqlDriverTest.FakeSqlDriver(program='!s*')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "program NOT LIKE 's%' ORDER BY id DESC LIMIT 10", drv.query)

    def test_should_filter_program_with_multiple_negative_conditions(self):
        drv = SqlDriverTest.FakeSqlDriver(program='!sshd !sudo')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "program <> 'sshd' AND program <> 'sudo' ORDER BY id DESC LIMIT 10",
            drv.query)

    def test_should_filter_program_with_positive_and_negative_conditions(self):
        drv = SqlDriverTest.FakeSqlDriver(program='!sshd s*')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "(program LIKE 's%') AND program <> 'sshd' ORDER BY id DESC LIMIT 10",
            drv.query)

    def test_should_filter_host_with_multiple_conditions(self):
        drv = SqlDriverTest.FakeSqlDriver(host='h1 h2')
        drv.prepare_query(100, True, 10)

        self.assertEqual("SELECT id, facility_num, level_num, host, datetime, "\
            "program, pid, message FROM logs WHERE id < 100 AND "\
            "(host = 'h1' OR host = 'h2') ORDER BY id DESC LIMIT 10",
            drv.query)
