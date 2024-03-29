from datetime import datetime
import os
import shutil
import numpy as np
import pandas as pd
import unittest

from nose.tools import raises
from osgeo import gdal

import utils

class UtilsDecompressTestCase(unittest.TestCase):
    
    @raises(ValueError)
    def test_decompress_invalid_type(self):
        utils.decompress('tests/files/dummy.csv', '/tmp/test_invalid_type')
    
    def test_decompress_tar(self):
        test_dir = '/tmp/test_tar'
        files = utils.decompress('tests/files/dummy.tar.gz', test_dir)
        self.assertEquals(files, [os.path.join(test_dir, 'dummy.csv')])
        shutil.rmtree(test_dir)

    def test_decompress_zip(self):
        test_dir = '/tmp/test_zip'
        files = utils.decompress('tests/files/dummy.zip', test_dir)
        self.assertEquals(files, [os.path.join(test_dir, 'dummy.csv')])
        shutil.rmtree(test_dir)

class DateTestCase(unittest.TestCase):
    
    @raises(ValueError)
    def test_invalid_date(self):
        utils.parse_date('200-01-13')

    def test_valid_date(self):
        self.assertEquals(utils.parse_date('2012-01-13'), datetime(2012,1,13))

    def test_filename2date(self):
        self.assertEquals(utils.filename2date('/tmp/4529_2012_222_ledaps.tif'), '2012-08-09')

class ParseEqnTestCase(unittest.TestCase):

    def test_no_match(self):
        self.assertEquals([], utils.parse_eqn_bands(''))
        self.assertEquals([], utils.parse_eqn_bands('12 - 4'))

    def test_match(self):
        self.assertEquals([1], utils.parse_eqn_bands('B1'))
        self.assertEquals(
            set([2,3,4,6]), 
            set(utils.parse_eqn_bands('(B2-B2)/(B3+B4)-B6'))
        )

class MultipleReplaceTestCase(unittest.TestCase):

    def test_replace(self):
        replacements = {'X': '3', 'Y': '2', 'Z': '1'}
        self.assertEquals(
            utils.multiple_replace('(X + Y) / (X-Y) = Z', replacements),
            '(3 + 2) / (3-2) = 1'
        )

class SerializeRastTestCase(unittest.TestCase):
    
    @raises(RuntimeError)
    def test_invalid_type(self):
        utils.serialize_rast('tests/files/dummy.csv').next()
    
    def test_no_extra_data(self):
        self.assertEquals(
            utils.serialize_rast('tests/files/dummy_single_band.tif').next(),
            (
                'POINT(-2097378.06273 2642045.53514)',
                {'val': 16000.0}
            )
        )

    def test_extra_data(self):
        extra = {'date': "2013-01-30"}
        self.assertEquals(
            utils.serialize_rast('tests/files/dummy_single_band.tif', extra).next(),
            (
                'POINT(-2097378.06273 2642045.53514)',
                {'date': '2013-01-30', 'val': 16000.0}
            )
        )

class RastUtilsTestCase(unittest.TestCase):

    def setUp(self):
        self.template_fn = 'tests/files/dummy_single_band.tif'
    
    def test_rast2array2rast(self):
        ds = gdal.Open(self.template_fn)
        array = utils.ds2array(ds)
        self.assertEquals(array.shape, (45, 54))
        rast_fn = utils.array2raster(array, self.template_fn)
        self.assertEqual(rast_fn, '/tmp/output_dummy_single_band.tif')
        os.remove(rast_fn)

    def test_rast2grid(self):
        out_fn = '/tmp/test_rast2grid.csv'
        utils.rast2grid(self.template_fn, out_fn)
        self.assertTrue(os.path.exists(out_fn))
        df = pd.read_csv(out_fn)
        wkts = df['pix_ctr_wkt']
        self.assertEquals(len(wkts), 2430)
        self.assertEquals(wkts[0], 'POINT(-2097378.06273 2642045.53514)')
        os.remove(out_fn)

    @raises(Exception)
    def test_array2raster_invalid_dim(self):
        ds = gdal.Open(self.template_fn)
        array = utils.ds2array(ds)
        utils.array2raster(array.transpose(), self.template_fn)

    def test_map_algebra(self):
        alg_fn = utils.rast_algebra(self.template_fn, 'B1/2')
        self.assertEquals(
            np.sum(utils.ds2array(gdal.Open(self.template_fn))) / 2,
            np.sum(utils.ds2array(gdal.Open(alg_fn)))
        )
        os.remove(alg_fn)

    def test_grid(self):
        grid = utils.rast2grid(self.template_fn)
        pix_data = list(utils.apply_grid(self.template_fn, grid, {'x': 'y'}))
        self.assertEqual(len(pix_data), 2430)
        os.remove(grid)


class AnalysisTestCase(unittest.TestCase):

    def spike_helper(self, l1, l2):
        dates = pd.date_range('1/1/2010', periods=len(l1), freq='A')
        s1, s2 = [pd.Series(data=x, index=dates) for x in [l1, l2]]
        np.testing.assert_array_equal(utils.despike(s1), s2)

    def test_timeseries2int_series(self):
        data=[1,2,3,4,5]
        ts = pd.Series(
            data=data, 
            index=pd.date_range('1/1/2010', periods=5, freq='A')
        )
        int_series = utils.timeseries2int_series(ts)
        np.testing.assert_array_equal(
            int_series,
            pd.Series(data=data, index=[0, 365, 731, 1096, 1461])
        )

    def test_dicts2timeseries(self):
        data = [
            {'date': '2012-09-01', 'val': 10.0},
            {'date': '2011-09-01', 'val': 5.0}
        ]
        series = utils.dicts2timeseries(data)
        self.assertTrue(np.array_equal(series.values, [5.0, 10.0]))

    def test_despike(self):
        self.spike_helper( 
            [1,1,1,5,1,1,1],
            [1,1,1,None,1,1,1]
        )

        self.spike_helper(
            [1,3,1,5,1,1,1],
            [1, None, 1, None, 1, 1, 1]
        )

    def test_least_squares(self):
        (m, c), sum_residuals = utils.least_squares(pd.Series([1, 2.1, 3, 4.4, 4.7]))

        self.assertAlmostEqual(m, 0.96999999999999997)
        self.assertAlmostEqual(c, 1.1000000000000008)
        self.assertAlmostEqual(sum_residuals, 0.24300000000000019)

    def test_segmented_least_squares(self):
        s1 = pd.Series([0, 0, 0, 1, 2, 3])
        s2 = pd.Series([0, 0, 0, 1, 1, 1, 3, 3])
        self.assertEquals(
            utils.segmented_least_squares(s1, 0.0001),
            [0, 2, 5]
        )
        self.assertEquals(
            utils.segmented_least_squares(s2, 0.0001),
            [0, 3, 6, 7]
        )

    def test_vertices2eqns(self):
        s = pd.Series([0, 0, 0, 1, 2, 3])
        v = pd.Series([True, False, True, False, False, True])
        expected = [
            (0.0, 0.0), 
            (0.0, 0.0), 
            (1.0000000000000002, -2.0000000000000031),
            (1.0000000000000002, -2.0000000000000031),
            (1.0000000000000002, -2.0000000000000031),
            (1.0000000000000002, -2.0000000000000031)
        ]

        for actual_value, expected_value in zip(utils.vertices2eqns(s, v), expected):
            np.testing.assert_almost_equal(actual_value, expected_value)

    def test_apply_eqn(self):
        self.assertEquals(utils.apply_eqn(5, (3, 2)), 17)

    def test_eqns2fitted_points(self):
        s = pd.Series([0, 0, 0, 1, 2, 4])
        eqns = [
            (0, 0),
            (0, 0),
            (1, -2.1),
            (1, -2.1),
            (1, -2.1),
            (1, -2.1)
        ]
        fit_series, fit_eqn = utils.eqns2fitted_points(s, eqns)
        fit_series = np.round(fit_series, 1)  # avoid floating point errors
        expected_series = [0, 0, 0, 0.9, 1.9, 2.9]
        expected_eqns = [
                (0, 0), (0, 0), (0, 0), (1, -2.1), (1, -2.1), (1, -2.1)]
        self.assertTrue(np.all(fit_series == expected_series))
        self.assertTrue(np.all(fit_eqn == expected_eqns))

    def test_get_idx(self):
        self.assertEquals(utils.get_idx(['a','b','c'], 1), 'b')
        self.assertEquals(utils.get_idx(pd.Series(['a','b','c']), 1), 'b')


    def assertAnalyzeEqual(self, line_cost, values, expected_out):

        # TODO - handle TrendLine

        for actual, expected in zip(list(utils.analyze(values, line_cost)), expected_out):
            self.assertEqual(sorted(actual.keys()), sorted(expected.keys()))

            for actual_key, actual_value in actual.items():
                expected_value = expected[actual_key]

                if actual_key.startswith('eqn'):
                    np.testing.assert_almost_equal(actual_value, expected_value)
                else:
                    self.assertAlmostEqual(actual_value, expected_value)

    def test_analyze_simple(self):
        line_cost = 2
        values = [
            {'date': '2010-12-31', 'val': 1},
            {'date': '2011-12-31', 'val': 2},
            {'date': '2012-12-31', 'val': 3},
            {'date': '2013-12-31', 'val': 4},
            {'date': '2014-12-31', 'val': 5},
            {'date': '2015-12-31', 'val': 7},
            {'date': '2016-12-31', 'val': 9},
            {'date': '2017-12-31', 'val': 11},
            {'date': '2018-12-31', 'val': 13},
            {'date': '2019-12-31', 'val': 15}
        ]
        expected_out = [
            {'eqn_fit': (0.0027374754316638297, 1.0000004496264048),  'eqn_right': (0.0027374754316638297, 1.0000004496264048),  'index_date': '2010-12-31',  'index_day': 0,  'spike': False,  'val_fit': 1.0000004496264048,  'val_raw': 1,  'vertex': True},
            {'eqn_fit': (0.0027374754316638297, 1.0000004496264048),  'eqn_right': (0.0027374754316638297, 1.0000004496264048),  'index_date': '2011-12-31',  'index_day': 365,  'spike': False,  'val_fit': 1.9991789821837025,  'val_raw': 2,  'vertex': False},
            {'eqn_fit': (0.0027374754316638297, 1.0000004496264048),  'eqn_right': (0.0027374754316638297, 1.0000004496264048),  'index_date': '2012-12-31',  'index_day': 731,  'spike': False,  'val_fit': 3.001094990172664,  'val_raw': 3,  'vertex': False},
            {'eqn_fit': (0.0027374754316638297, 1.0000004496264048),  'eqn_right': (0.0027374754316638297, 1.0000004496264048),  'index_date': '2013-12-31',  'index_day': 1096,  'spike': False,  'val_fit': 4.0002735227299624,  'val_raw': 4,  'vertex': False},
            {'eqn_fit': (0.0054760218598211806, -3.0009885655254509),  'eqn_right': (0.0054760218598211806, -3.0009885655254509),  'index_date': '2014-12-31',  'index_day': 1461,  'spike': False,  'val_fit': 4.9994793716732948,  'val_raw': 5,  'vertex': True},
            {'eqn_fit': (0.0054760218598211806, -3.0009885655254509),  'eqn_right': (0.0054760218598211806, -3.0009885655254509),  'index_date': '2015-12-31',  'index_day': 1826,  'spike': False,  'val_fit': 6.9982273505080252,  'val_raw': 7,  'vertex': False},
            {'eqn_fit': (0.0054760218598211806, -3.0009885655254509),  'eqn_right': (0.0054760218598211806, -3.0009885655254509),  'index_date': '2016-12-31',  'index_day': 2192,  'spike': False,  'val_fit': 9.002451351202577,  'val_raw': 9,  'vertex': False},
            {'eqn_fit': (0.0054760218598211806, -3.0009885655254509),  'eqn_right': (0.0054760218598211806, -3.0009885655254509),  'index_date': '2017-12-31',  'index_day': 2557,  'spike': False,  'val_fit': 11.001199330037309,  'val_raw': 11,  'vertex': False},
            {'eqn_fit': (0.0054760218598211806, -3.0009885655254509),  'eqn_right': (0.0054760218598211806, -3.0009885655254509),  'index_date': '2018-12-31',  'index_day': 2922,  'spike': False,  'val_fit': 12.999947308872041,  'val_raw': 13,  'vertex': False},
            {'eqn_fit': (0.0054760218598211806, -3.0009885655254509),  'eqn_right': (0.0054760218598211806, -3.0009885655254509),  'index_date': '2019-12-31',  'index_day': 3287,  'spike': False,  'val_fit': 14.99869528770677,  'val_raw': 15,  'vertex': True}
        ]
        
        #self.assertAnalyzeEqual(line_cost, values, expected_out)

    def test_analyze_simple_spike(self):
        line_cost = 2
        values = [
            {'date': '2010-12-31', 'val': 1},
            {'date': '2011-12-31', 'val': 2},
            {'date': '2012-12-31', 'val': 3},
            {'date': '2013-12-31', 'val': 4},
            {'date': '2014-12-31', 'val': 1000},
            {'date': '2015-12-31', 'val': 7},
            {'date': '2016-12-31', 'val': 9},
            {'date': '2017-12-31', 'val': 11},
            {'date': '2018-12-31', 'val': 13},
            {'date': '2019-12-31', 'val': 15}
        ]

        expected_out = [
            {'eqn_fit': (0.0032558793548741337, 0.78357535042314486),  'eqn_right': (0.0032558793548741337, 0.78357535042314486),  'index_date': '2010-12-31',  'index_day': 0,  'spike': False,  'val_fit': 0.78357535042314486,  'val_raw': 1,  'vertex': True},
            {'eqn_fit': (0.0032558793548741337, 0.78357535042314486),  'eqn_right': (0.0032558793548741337, 0.78357535042314486),  'index_date': '2011-12-31',  'index_day': 365,  'spike': False,  'val_fit': 1.9719713149522036,  'val_raw': 2,  'vertex': False},
            {'eqn_fit': (0.0032558793548741337, 0.78357535042314486),  'eqn_right': (0.0032558793548741337, 0.78357535042314486),  'index_date': '2012-12-31',  'index_day': 731,  'spike': False,  'val_fit': 3.1636231588361365,  'val_raw': 3,  'vertex': False},
            {'eqn_fit': (0.0032558793548741337, 0.78357535042314486),  'eqn_right': (0.0032558793548741337, 0.78357535042314486),  'index_date': '2013-12-31',  'index_day': 1096,  'spike': False,  'val_fit': 4.3520191233651957,  'val_raw': 4,  'vertex': False},
            {'eqn_fit': (0.0032558793548741337, 0.78357535042314486),  'eqn_right': (0.0032558793548741337, 0.78357535042314486),  'index_date': '2014-12-31',  'index_day': 1461,  'spike': True,  'val_fit': 5.540415087894254,  'val_raw': 1000,  'vertex': False},
            {'eqn_fit': (0.0054764496171133877, -3.0021863810355005),  'eqn_right': (0.0054764496171133877, -3.0021863810355005),  'index_date': '2015-12-31',  'index_day': 1826,  'spike': False,  'val_fit': 6.9978106198135457,  'val_raw': 7,  'vertex': True},
            {'eqn_fit': (0.0054764496171133877, -3.0021863810355005),  'eqn_right': (0.0054764496171133877, -3.0021863810355005),  'index_date': '2016-12-31',  'index_day': 2192,  'spike': False,  'val_fit': 9.0021911796770464,  'val_raw': 9,  'vertex': False},
            {'eqn_fit': (0.0054764496171133877, -3.0021863810355005),  'eqn_right': (0.0054764496171133877, -3.0021863810355005),  'index_date': '2017-12-31',  'index_day': 2557,  'spike': False,  'val_fit': 11.001095289923432,  'val_raw': 11,  'vertex': False},
            {'eqn_fit': (0.0054764496171133877, -3.0021863810355005),  'eqn_right': (0.0054764496171133877, -3.0021863810355005),  'index_date': '2018-12-31',  'index_day': 2922,  'spike': False,  'val_fit': 12.99999940016982,  'val_raw': 13,  'vertex': False},
            {'eqn_fit': (0.0054764496171133877, -3.0021863810355005),  'eqn_right': (0.0054764496171133877, -3.0021863810355005),  'index_date': '2019-12-31',  'index_day': 3287,  'spike': False,  'val_fit': 14.998903510416206,  'val_raw': 15,  'vertex': True}
        ]

        #self.assertAnalyzeEqual(line_cost, values, expected_out)
