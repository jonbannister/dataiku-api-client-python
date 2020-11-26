import re

from ..utils import DataikuException
from ..utils import DataikuUTF8CSVReader
from ..utils import DataikuStreamedHttpUTF8CSVReader
from .utils import is_basestring
import json, warnings
import time
from .metrics import ComputedMetrics
from .utils import DSSDatasetSelectionBuilder, DSSFilterBuilder
from .future import DSSFuture

class PredictionSplitParamsHandler(object):
    """Object to modify the train/test splitting params."""

    SPLIT_PARAMS_KEY = 'splitParams'

    def __init__(self, mltask_settings):
        """Do not call directly, use :meth:`DSSMLTaskSettings.get_split_params`"""
        self.mltask_settings = mltask_settings

    def get_raw(self):
        """Gets the raw settings of the prediction split configuration. This returns a reference to the raw settings, not a copy,
        so changes made to the returned object will be reflected when saving.

        :rtype: dict
        """
        return self.mltask_settings[PredictionSplitParamsHandler.SPLIT_PARAMS_KEY]


    def set_split_random(self, train_ratio = 0.8, selection = None, dataset_name=None):
        """
        Sets the train/test split to random splitting of an extract of a single dataset

        :param float train_ratio: Ratio of rows to use for train set. Must be between 0 and 1
        :param object selection: A :class:`~dataikuapi.dss.utils.DSSDatasetSelectionBuilder` to build the settings of the extract of the dataset. May be None (won't be changed)
        :param str dataset_name: Name of dataset to split. If None, the main dataset used to create the visual analysis will be used.
        """
        sp = self.mltask_settings[PredictionSplitParamsHandler.SPLIT_PARAMS_KEY]
        sp["ttPolicy"] = "SPLIT_SINGLE_DATASET"
        if selection is not None:
            if isinstance(selection, DSSDatasetSelectionBuilder):
                sp["ssdSelection"] = selection.build()
            else:
                sp["ssdSelection"] = selection

        sp["ssdTrainingRatio"] = train_ratio
        sp["kfold"] = False

        if dataset_name is not None:
            sp["ssdDatasetSmartName"] = dataset_name

        return self

    def set_split_kfold(self, n_folds = 5, selection = None, dataset_name=None):
        """
        Sets the train/test split to k-fold splitting of an extract of a single dataset

        :param int n_folds: number of folds. Must be greater than 0
        :param object selection: A :class:`~dataikuapi.dss.utils.DSSDatasetSelectionBuilder` to build the settings of the extract of the dataset. May be None (won't be changed)
        :param str dataset_name: Name of dataset to split. If None, the main dataset used to create the visual analysis will be used.
        """
        sp = self.mltask_settings[PredictionSplitParamsHandler.SPLIT_PARAMS_KEY]
        sp["ttPolicy"] = "SPLIT_SINGLE_DATASET"
        if selection is not None:
            if isinstance(selection, DSSDatasetSelectionBuilder):
                sp["ssdSelection"] = selection.build()
            else:
                sp["ssdSelection"] = selection

        sp["kfold"] = True
        sp["nFolds"] = n_folds

        if dataset_name is not None:
            sp["ssdDatasetSmartName"] = dataset_name

        return self

    def set_split_explicit(self, train_selection, test_selection, dataset_name=None, test_dataset_name=None, train_filter=None, test_filter=None):
        """
        Sets the train/test split to explicit extract of one or two dataset(s)

        :param object train_selection: A :class:`~dataikuapi.dss.utils.DSSDatasetSelectionBuilder` to build the settings of the extract of the train dataset. May be None (won't be changed)
        :param object test_selection: A :class:`~dataikuapi.dss.utils.DSSDatasetSelectionBuilder` to build the settings of the extract of the test dataset. May be None (won't be changed)
        :param str dataset_name: Name of dataset to use for the extracts. If None, the main dataset used to create the ML Task will be used.
        :param str test_dataset_name: Name of a second dataset to use for the test data extract. If None, both extracts are done from dataset_name
        :param object train_filter: A :class:`~dataikuapi.dss.utils.DSSFilterBuilder` to build the settings of the filter of the train dataset. May be None (won't be changed)
        :param object test_filter: A :class:`~dataikuapi.dss.utils.DSSFilterBuilder` to build the settings of the filter of the test dataset. May be None (won't be changed)
        """
        sp = self.mltask_settings[PredictionSplitParamsHandler.SPLIT_PARAMS_KEY]
        if dataset_name is None:
            raise Exception("For explicit splitting a dataset_name is mandatory")
        if test_dataset_name is None or test_dataset_name == dataset_name:
            sp["ttPolicy"] = "EXPLICIT_FILTERING_SINGLE_DATASET"
            train_split ={}
            test_split = {}
            sp['efsdDatasetSmartName'] = dataset_name
            sp['efsdTrain'] = train_split
            sp['efsdTest'] = test_split
        else:
            sp["ttPolicy"] = "EXPLICIT_FILTERING_TWO_DATASETS"
            train_split ={'datasetSmartName' : dataset_name}
            test_split = {'datasetSmartName' : test_dataset_name}
            sp['eftdTrain'] = train_split
            sp['eftdTest'] = test_split

        if train_selection is not None:
            if isinstance(train_selection, DSSDatasetSelectionBuilder):
                train_split["selection"] = train_selection.build()
            else:
                train_split["selection"] = train_selection
        if test_selection is not None:
            if isinstance(test_selection, DSSDatasetSelectionBuilder):
                test_split["selection"] = test_selection.build()
            else:
                test_split["selection"] = test_selection

        if train_filter is not None:
            if isinstance(train_filter, DSSFilterBuilder):
                train_split["filter"] = train_filter.build()
            else:
                train_split["filter"] = train_filter
        if test_filter is not None:
            if isinstance(test_filter, DSSFilterBuilder):
                test_split["filter"] = test_filter.build()
            else:
                test_split["filter"] = test_filter

        return self

    def set_time_ordering(self, feature_name, ascending=True):
        """
        Uses a variable to sort the data for train/test split and hyperparameter optimization by time
        :param str feature_name: Name of the variable to use
        :param bool ascending: True iff the test set is expected to have larger time values than the train set
        """
        self.unset_time_ordering()
        if not feature_name in self.mltask_settings["preprocessing"]["per_feature"]:
            raise ValueError("Feature %s doesn't exist in this ML task, can't use as time" % feature_name)
        self.mltask_settings['time']['enabled'] = True
        self.mltask_settings['time']['timeVariable'] = feature_name
        self.mltask_settings['time']['ascending'] = ascending
        self.mltask_settings['preprocessing']['per_feature'][feature_name]['missing_handling'] = "DROP_ROW"
        if self.mltask_settings['splitParams']['ttPolicy'] == "SPLIT_SINGLE_DATASET":
            self.mltask_settings['splitParams']['ssdSplitMode'] = "SORTED"
            self.mltask_settings['splitParams']['ssdColumn'] = feature_name
        if self.mltask_settings['modeling']['gridSearchParams']['mode'] == "KFOLD":
            self.mltask_settings['modeling']['gridSearchParams']['mode'] = "TIME_SERIES_KFOLD"
        elif self.mltask_settings['modeling']['gridSearchParams']['mode'] == "SHUFFLE":
            self.mltask_settings['modeling']['gridSearchParams']['mode'] = "TIME_SERIES_SINGLE_SPLIT"

        return self

    def unset_time_ordering(self):
        """
        Remove time-based ordering for train/test split and hyperparameter optimization
        """
        self.mltask_settings['time']['enabled'] = False
        self.mltask_settings['time']['timeVariable'] = None
        if self.mltask_settings['splitParams']['ttPolicy'] == "SPLIT_SINGLE_DATASET":
            self.mltask_settings['splitParams']['ssdSplitMode'] = "RANDOM"
            self.mltask_settings['splitParams']['ssdColumn'] = None
        if self.mltask_settings['modeling']['gridSearchParams']['mode'] == "TIME_SERIES_KFOLD":
            self.mltask_settings['modeling']['gridSearchParams']['mode'] = "KFOLD"
        elif self.mltask_settings['modeling']['gridSearchParams']['mode'] == "TIME_SERIES_SINGLE_SPLIT":
            self.mltask_settings['modeling']['gridSearchParams']['mode'] = "SHUFFLE"

        return self


class DSSMLTaskSettings(object):
    """
    Object to read and modify the settings of a ML task.

    Do not create this object directly, use :meth:`DSSMLTask.get_settings()` instead
    """
    def __init__(self, client, project_key, analysis_id, mltask_id, mltask_settings):
        self.client = client
        self.project_key = project_key
        self.analysis_id = analysis_id
        self.mltask_id = mltask_id
        self.mltask_settings = mltask_settings

    def get_raw(self):
        """
        Gets the raw settings of this ML Task. This returns a reference to the raw settings, not a copy,
        so changes made to the returned object will be reflected when saving.

        :rtype: dict
        """
        return self.mltask_settings

    def get_feature_preprocessing(self, feature_name):
        """
        Gets the feature preprocessing params for a particular feature. This returns a reference to the
        feature's settings, not a copy, so changes made to the returned object will be reflected when saving

        :return: A dict of the preprocessing settings for a feature
        :rtype: dict 
        """
        return self.mltask_settings["preprocessing"]["per_feature"][feature_name]

    def foreach_feature(self, fn, only_of_type = None):
        """
        Applies a function to all features (except target)

        :param function fn: Function that takes 2 parameters: feature_name and feature_params and returns modified feature_params
        :param str only_of_type: if not None, only applies to feature of the given type. Can be one of ``CATEGORY``, ``NUMERIC``, ``TEXT`` or ``VECTOR``
        """
        import copy
        new_per_feature = {}
        for (k, v) in self.mltask_settings["preprocessing"]["per_feature"].items():
            if v["role"] == "TARGET" or (only_of_type is not None and v["type"] != only_of_type):
                new_per_feature[k] = v
            else:
                new_per_feature[k] = fn(k, copy.deepcopy(v))
        self.mltask_settings["preprocessing"]["per_feature"] = new_per_feature

    def reject_feature(self, feature_name):
        """
        Marks a feature as rejected and not used for training
        :param str feature_name: Name of the feature to reject
        """
        self.get_feature_preprocessing(feature_name)["role"] = "REJECT"

    def use_feature(self, feature_name):
        """
        Marks a feature as input for training
        :param str feature_name: Name of the feature to reject
        """
        self.get_feature_preprocessing(feature_name)["role"] = "INPUT"

    def get_algorithm_settings(self, algorithm_name):
        """
        Gets the training settings for a particular algorithm. This returns a reference to the
        algorithm's settings, not a copy, so changes made to the returned object will be reflected when saving.

        This method returns a dictionary of the settings for this algorithm.
        All algorithm dicts have at least an "enabled" key in the dictionary.
        The 'enabled' key indicates whether this algorithm will be trained

        Other settings are algorithm-dependent and are the various hyperparameters of the 
        algorithm. The precise keys for each algorithm are not all documented. You can print
        the returned dictionary to learn more about the settings of each particular algorithm

        Please refer to the documentation for details on available algorithms.

        :param str algorithm_name: Name (in capitals) of the algorithm.
        :return: An AlgortihmSettings (extended dict) for an algorithm.
        :rtype: AlgorithmSettings
        """
        algorithm_settings_class = AlgorithmSettings
        if algorithm_name in self.__class__.algorithm_remap:
            algorithm_meta = self.__class__.algorithm_remap[algorithm_name]
            algorithm_name = algorithm_meta.algorithm_name
            algorithm_settings_class = algorithm_meta.algorithm_settings_class

        algorithm_settings = self.mltask_settings["modeling"][algorithm_name.lower()]
        raw_hyperparameter_search_params = self.mltask_settings["modeling"]["gridSearchParams"]
        if not isinstance(algorithm_settings, AlgorithmSettings):
            algorithm_params = algorithm_settings_class(algorithm_settings, raw_hyperparameter_search_params)
            # Subsequent calls get the same object
            self.mltask_settings["modeling"][algorithm_name.lower()] = algorithm_params
        return algorithm_settings

    def set_algorithm_enabled(self, algorithm_name, enabled):
        """
        Enables or disables an algorithm based on its name.

        Please refer to the documentation for details on available algorithms.

        :param str algorithm_name: Name (in capitals) of the algorithm.
        """
        self.get_algorithm_settings(algorithm_name)["enabled"] = enabled

    def disable_all_algorithms(self):
        """Disables all algorithms"""

        for algorithm_name in self.__class__.algorithm_remap.keys():
            key = self.__class__.algorithm_remap[algorithm_name]
            if key in self.mltask_settings["modeling"]:
                self.mltask_settings["modeling"][key]["enabled"] = False

        for custom_mllib in self.mltask_settings["modeling"]["custom_mllib"]:
            custom_mllib["enabled"] = False
        for custom_python in self.mltask_settings["modeling"]["custom_python"]:
            custom_python["enabled"] = False
        for plugin in self.mltask_settings["modeling"]["plugin_python"].values():
            plugin["enabled"] = False

    def get_all_possible_algorithm_names(self):
        """
        Returns the list of possible algorithm names, i.e. the list of valid
        identifiers for :meth:`set_algorithm_enabled` and :meth:`get_algorithm_settings`

        This does not include Custom Python models, Custom MLLib models, plugin models.
        This includes all possible algorithms, regardless of the prediction kind (regression/classification)
        or engine, so some algorithms may be irrelevant

        :returns: the list of algorithm names as a list of strings
        :rtype: list of string
        """
        return self.__class__.algorithm_remap.keys()

    def get_enabled_algorithm_names(self):
        """
        :returns: the list of enabled algorithm names as a list of strings
        :rtype: list of string
        """
        algos = self.__class__.algorithm_remap
        return [algorithm_name for algorithm_name in algos.keys() if self.mltask_settings["modeling"][algos[algorithm_name].algorithm_name.lower()]["enabled"]]

    def get_enabled_algorithm_settings(self):
        """
        :returns: the map of enabled algorithm names with their settings
        :rtype: dict
        """
        return {key: self.get_algorithm_settings(key) for key in self.get_enabled_algorithm_names()}

    def set_metric(self, metric=None, custom_metric=None, custom_metric_greater_is_better=True, custom_metric_use_probas=False):
        """
        Sets the score metric to optimize for a prediction ML Task

        :param str metric: metric to use. Leave empty to use a custom metric. You need to set the ``custom_metric`` value in that case
        :param str custom_metric: code of the custom metric
        :param bool custom_metric_greater_is_better: whether the custom metric is a score or a loss
        :param bool custom_metric_use_probas: whether to use the classes' probas or the predicted value (for classification)
        """
        if custom_metric is None and metric is None:
            raise ValueError("Either metric or custom_metric must be defined")
        self.mltask_settings["modeling"]["metrics"]["evaluationMetric"] = metric if custom_metric is None else 'CUSTOM'
        self.mltask_settings["modeling"]["metrics"]["customEvaluationMetricCode"] = custom_metric
        self.mltask_settings["modeling"]["metrics"]["customEvaluationMetricGIB"] = custom_metric_greater_is_better
        self.mltask_settings["modeling"]["metrics"]["customEvaluationMetricNeedsProba"] = custom_metric_use_probas

    def get_hyperparameter_search_settings(self):
        return HyperparameterSearchSettings(self.mltask_settings["modeling"]["gridSearchParams"])

    def save(self):
        """Saves back these settings to the ML Task"""

        self.client._perform_empty(
                "POST", "/projects/%s/models/lab/%s/%s/settings" % (self.project_key, self.analysis_id, self.mltask_id),
                body = self.mltask_settings)


class HyperparameterSearchSettings(object):

    def __init__(self, raw_settings):
        self._raw_settings = raw_settings

    def _key_repr(self, key):
        if is_basestring(self._raw_settings[key]):
            return "    \"{}\"=\"{}\"\n".format(key, self._raw_settings[key])
        else:
            return "    \"{}\"={}\n".format(key, self._raw_settings[key])

    def _repr_html_(self):

        res = "<pre>"
        res += self.__class__.__name__ + "(\n"
        res += "Search Strategy:\n"
        res += self._key_repr("strategy")
        if self._raw_settings["strategy"] == "BAYESIAN":
            res += self._key_repr("bayesianOptimizer")

        res += "Search Validation:\n"
        res += self._key_repr("mode")
        if self._raw_settings["mode"] in {"SHUFFLE", "TIME_SERIES_SINGLE_SPLIT"}:
            res += self._key_repr("splitRatio")
        elif self._raw_settings["mode"] in {"KFOLD", "TIME_SERIES_KFOLD"}:
            res += self._key_repr("nFolds")

        res += self._key_repr("stratified")
        # TODO: pointers to ssdSeed and time variable ?

        res += "Execution Settings:\n"
        if self._raw_settings.get("timeout", 0) > 0:
            res += self._key_repr("timeout")
        if self._raw_settings["strategy"] == "GRID":
            res += self._key_repr("nIter")
            res += self._key_repr("randomized")
            if self._raw_settings.get("randomized", False):
                res += self._key_repr("seed")
        else:
            # RANDOM and BAYESIAN search strategies
            res += self._key_repr("nIterRandom")
            res += self._key_repr("seed")

        res += "Parallelism Settings:\n"
        res += self._key_repr("nJobs")
        res += self._key_repr("distributed")
        if self._raw_settings.get("distributed", False):
            res += self._key_repr("nContainers")
        res += ")</pre>"
        res += "<details><pre>{}</pre></details>".format(self.__repr__())
        return res

    def __repr__(self):
        return self.__class__.__name__ + "(settings={})".format(json.dumps(self._raw_settings, indent=4))

    __str__ = __repr__

    def _set_seed(self, seed):
        if seed is not None:
            if not isinstance(seed, int):
                warnings.warn("HyperparameterSearchSettings ignoring invalid input: seed")
                warnings.warn("seed must be an integer")
            else:
                self._raw_settings["seed"] = seed

    @property
    def strategy(self):
        return self._raw_settings["strategy"]

    @strategy.setter
    def strategy(self, strategy):
        assert strategy in {"GRID", "RANDOM", "BAYESIAN"}
        self._raw_settings["strategy"] = strategy

    def set_strategy_to_grid_search(self, shuffle=None, seed=None):
        self._raw_settings["strategy"] = "GRID"
        if shuffle is not None:
            if not isinstance(shuffle, bool):
                warnings.warn()
            else:
                self._raw_settings["randomized"] = shuffle
        self._set_seed(seed)

    def set_strategy_to_random_search(self, seed=None):
        self._raw_settings["strategy"] = "RANDOM"
        self._set_seed(seed)

    def set_strategy_to_bayesian_search(self, seed=None):
        self._raw_settings["strategy"] = "BAYESIAN"
        self._set_seed(seed)

    @property
    def validation_mode(self):
        return self._raw_settings["mode"]

    @validation_mode.setter
    def validation_mode(self, mode):
        assert mode in {"KFOLD", "SHUFFLE", "TIME_SERIES_KFOLD", "TIME_SERIES_SINGLE_SPLIT", "CUSTOM"}
        self._raw_settings["mode"] = mode

    def set_validation_mode_to_kfold(self, n_folds=None, stratified=None):
        if self._raw_settings["mode"] == "TIME_SERIES_SINGLE_SPLIT":
            self._raw_settings["mode"] = "TIME_SERIES_KFOLD"
        else:
            self._raw_settings["mode"] = "KFOLD"
        if n_folds is not None:
            if not (isinstance(n_folds, int) and n_folds > 0):
                warnings.warn("HyperparameterSearchSettings.set_validation_mode_to_kfold ignoring invalid input: n_folds")
                warnings.warn("n_folds must be a positive integer")
                self._raw_settings["nFolds"] = n_folds
        if stratified is not None:
            if not isinstance(stratified, bool):
                warnings.warn("HyperparameterSearchSettings.set_validation_mode_to_kfold ignoring invalid input: stratified")
                warnings.warn("stratified must be a boolean")
            else:
                self._raw_settings["stratified"] = stratified

    def set_validation_mode_to_single_split(self, split_ratio=None, stratified=None):
        if self._raw_settings["mode"] == "TIME_SERIES_KFOLD":
            self._raw_settings["mode"] = "TIME_SERIES_SINGLE_SPLIT"
        else:
            self._raw_settings["mode"] = "SHUFFLE"
        if split_ratio is not None:
            if not (isinstance(split_ratio, float) and split_ratio > 0 and split_ratio < 1):
                warnings.warn("HyperparameterSearchSettings.set_validation_mode_to_single_split ignoring invalid input: split_ratio")
                warnings.warn(" split_ratio must be float between 0 and 1")
            self._raw_settings["splitRatio"] = split_ratio
        if stratified is not None:
            if not isinstance(stratified, bool):
                warnings.warn("HyperparameterSearchSettings.set_validation_mode_to_single_split ignoring invalid input: stratified")
                warnings.warn("stratified must be a boolean")
            else:
                self._raw_settings["stratified"] = stratified

    def set_validation_mode_to_custom(self, code=None):
        self._raw_settings["mode"] = "CUSTOM"
        if code is not None:
            if not is_basestring(code):
                warnings.warn("HyperparameterSearchSettings.set_validation_mode_to_custom ignoring invalid input: code")
                warnings.warn("code must be a Python interpretable string")
            self._raw_settings["code"] = code

    def set_search_distribution(self, distributed, n_containers=None):
        assert isinstance(distributed, bool)
        if n_containers is not None:
            assert isinstance(n_containers, int)
            self._raw_settings["nContainers"] = n_containers
        self._raw_settings["distributed"] = distributed

    @property
    def timeout(self):
        return self._raw_settings["timeout"]

    @timeout.setter
    def timeout(self, timeout):
        assert isinstance(timeout, int)
        self._raw_settings["timeout"] = timeout

    @property
    def n_iter(self):
        if self._raw_settings["strategy"] == "GRID":
            return self._raw_settings["nIter"]
        else:
            # RANDOM and BAYESIAN search strategies
            return self._raw_settings["nIterRandom"]

    @n_iter.setter
    def n_iter(self, n_iter):
        assert isinstance(n_iter, int)
        if self._raw_settings["strategy"] == "GRID":
            self._raw_settings["nIter"] = n_iter
        else:
            self._raw_settings["nIterRandom"] = n_iter

    @property
    def parallelism(self):
        return self._raw_settings["nJobs"]

    @parallelism.setter
    def parallelism(self, n_jobs):
        self._raw_settings["nJobs"] = n_jobs


class HyperparameterSettings(object):

    def __init__(self, name, algo_settings):
        self.name = name
        self._algo_settings = algo_settings


class NumericalHyperparameterSettings(HyperparameterSettings):

    def _repr_html_(self):
        active_dict = self._algo_settings._get_active_numerical_hyperparam_dict(self.name)
        return "<pre>" + self.__class__.__name__ + "(hyperparameter=\"{}\", settings={})</pre>".format(self.name, json.dumps(active_dict, indent=4)) + \
               "\n<details><pre>{}</pre></details>".format(self.__repr__())

    def __repr__(self):
        raw_dict = self._algo_settings[self.name]
        return self.__class__.__name__ + "(hyperparameter=\"{}\", settings={})".format(self.name, json.dumps(raw_dict, indent=4))

    __str__ = __repr__

    def set_explicit_values(self, values, set_mode_to_explicit=True):
        self._algo_settings._set_numerical_explicit_values(self.name, values, set_mode_to_explicit=set_mode_to_explicit)

    def set_range(self, range_min=None, range_max=None, nb_values=None, set_mode_to_range=True):
        self._algo_settings._set_numerical_range(self.name, range_min=range_min, range_max=range_max, nb_values=nb_values,
                                                 set_mode_to_range=set_mode_to_range)

    def set_mode_to_explicit(self):
        self._algo_settings._set_hyperparameter_mode_to_explicit(self.name)

    def set_mode_to_range(self):
        self._algo_settings._set_hyperparameter_mode_to_range(self.name)


class CategoricalHyperparameterSettings(HyperparameterSettings):

    def __repr__(self):
        return self.__class__.__name__ + "(hyperparameter=\"{}\", settings={})".format(self.name, json.dumps(self._algo_settings[self.name], indent=4))

    __str__ = __repr__

    def set_values(self, values=None):
        self._algo_settings._set_categorical_values(self.name, values=values)

    def enable_categories(self, categories, disable_others=False):
        accepted_categories = self._algo_settings[self.name]["values"].keys()
        for category in categories:
            assert is_basestring(category)
            assert category in accepted_categories
        self.set_values({category: {"enabled": True}
                         for category in categories})
        if disable_others:
            self.set_values({category: {"enabled": False}
                             for category in accepted_categories
                             if category not in categories})

    def disable_categories(self, categories, enable_others=False):
        accepted_categories = self._algo_settings[self.name]["values"].keys()
        for category in categories:
            assert is_basestring(category)
            assert category in accepted_categories
        self.set_values({category: {"enabled": False}
                         for category in categories})
        if enable_others:
            self.set_values({category: {"enabled": True}
                             for category in accepted_categories
                             if category not in categories})


class SingleValuedHyperparameterSettings(HyperparameterSettings):

    def __init__(self, name, algo_settings, accepted_values=None, accepted_types=None):
        super(SingleValuedHyperparameterSettings, self).__init__(name, algo_settings)
        self.accepted_values = accepted_values
        self.accepted_types = accepted_types

    def __repr__(self):
        if self.accepted_values is not None:
            if is_basestring(self._algo_settings[self.name]):
                return self.__class__.__name__ + "(hyperparameter=\"{}\", value=\"{}\", accepted_values={})".format(self.name,
                                                                                                                    self._algo_settings[self.name],
                                                                                                                    json.dumps(self.accepted_values))
            else:
                return self.__class__.__name__ + "(hyperparameter=\"{}\", value={}, accepted_values={})".format(self.name,
                                                                                                                    self._algo_settings[self.name],
                                                                                                                    str(self.accepted_values))
        else:
            return self.__class__.__name__ + "(hyperparameter=\"{}\", value={})".format(self.name, self._algo_settings[self.name])

    __str__ = __repr__

    def set_value(self, value):
        if self.accepted_values is not None:
            assert value in self.accepted_values, "Invalid value for hyperparameter {}. Must be in {}".format(self.name, json.dumps(self.accepted_values))
        if self.accepted_types is not None:
            assert any(isinstance(value, type) for type in self.accepted_types), "Invalid type for hyperparameter {}. Type must be one of {}".format(self.name, self.accepted_types)
        self._algo_settings._set_single_valued_hyperparameter(self.name, value)


class AlgorithmSettings(dict):

    excluded_keys = {"enabled"}

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(AlgorithmSettings, self).__init__(raw_settings)
        self._hyperparameter_search_params = hyperparameter_search_params

    def _repr_html_(self):
        active_settings = dict()
        for key in self.keys():
            if isinstance(self[key], dict):
                # Searchable hyperparameter
                if "range" in self[key]:
                    # Numerical hyperparameter
                    active_hyperparam = self._get_active_numerical_hyperparam_dict(key)
                else:
                    # Categorical hyperparameter
                    active_hyperparam = self[key]
                active_settings[key] = active_hyperparam
            else:
                active_settings[key] = self[key]
        return "<pre>" + self.__class__.__name__ + "(active_values={})</pre>".format(json.dumps(active_settings, indent=4)) + \
               "\n<details><pre>{}</pre></details>".format(self.__repr__())

    def __repr__(self):
        return self.__class__.__name__ + "(values={})".format(json.dumps(super(AlgorithmSettings, self).copy(), indent=4))

    __str__ = __repr__

    def _get_active_numerical_hyperparam_dict(self, hyperparameter_name):
        clean_hyperparam = dict()
        raw_hyperparam = self[hyperparameter_name]
        mode = self._get_hyperparameter_mode(hyperparameter_name)
        if mode == "EXPLICIT":
            clean_hyperparam["values"] = raw_hyperparam["values"]
        else:
            clean_hyperparam["range"] = raw_hyperparam["range"]
        if self.strategy == "GRID":
            clean_hyperparam["gridMode"] = raw_hyperparam["gridMode"]
        else:
            # RANDOM and BAYESIAN strategies
            clean_hyperparam["randomMode"] = raw_hyperparam["randomMode"]
        return clean_hyperparam

    def _get_all_hyperparameter_names(self):
        return [key for key in self.keys() if key not in self.excluded_keys]

    @property
    def enabled(self):
        return self["enabled"]

    @enabled.setter
    def enabled(self, enabled):
        assert isinstance(enabled, bool), "enabled property must be a boolean"
        self["enabled"] = enabled

    def _set_single_valued_hyperparameter(self, hyperparameter_name, value):
        self._check_hyperparameter_name(hyperparameter_name)
        if is_basestring(self[hyperparameter_name]):
            assert is_basestring(value), "Invalid input type for hyperparameter \"{}\": expected a string".format(hyperparameter_name)
        elif isinstance(self[hyperparameter_name], int) or isinstance(self[hyperparameter_name], float):
            assert isinstance(value, int) or isinstance(value, float), "Invalid input type for hyperparameter \"{}\": expected a number".format(hyperparameter_name)
        else:
            raise ValueError("Hyperparameter \"{}\" is not single valued".format(hyperparameter_name))
        self[hyperparameter_name] = value

    def _set_hyperparameter_mode_to_range(self, hyperparameter_name):
        self._check_hyperparameter_name(hyperparameter_name)
        self._check_hyperparameter_searchable(hyperparameter_name)
        self._check_hyperparameter_numerical(hyperparameter_name)
        self[hyperparameter_name]["gridMode"] = "RANGE"
        self[hyperparameter_name]["randomMode"] = "RANGE"

    def _set_hyperparameter_mode_to_explicit(self, hyperparameter_name):
        self._check_hyperparameter_name(hyperparameter_name)
        self._check_hyperparameter_searchable(hyperparameter_name)
        self._check_hyperparameter_numerical(hyperparameter_name)
        self[hyperparameter_name]["gridMode"] = "EXPLICIT"
        self[hyperparameter_name]["randomMode"] = "EXPLICIT"

    def _set_numerical_explicit_values(self, hyperparameter_name, values, set_mode_to_explicit=True):
        self._check_hyperparameter_name(hyperparameter_name)
        error_message = "Invalid values input type for hyperparameter " \
                        "\"{}\": ".format(hyperparameter_name) + \
                        " expecting a non-empty list of numbers"
        assert values is not None and isinstance(values, list) and len(values) > 0, error_message
        for val in values:
            assert isinstance(val, int) or isinstance(val, float), error_message
        limit_min = self[hyperparameter_name]["limit"].get("min")
        if limit_min is not None:
            assert all(limit_min <= val for val in values), "Value(s) below hyperparameter \"{}\" limit {}".format(hyperparameter_name, limit_min)
        limit_max = self[hyperparameter_name]["limit"].get("max")
        if limit_max is not None:
            assert all(val <= limit_max for val in values), "Value(s) above hyperparameter \"{}\" limit {}".format(hyperparameter_name, limit_max)
        if len(set(values)) < len(values):
                warnings.warn("Detected duplicates in provided values: " + str(sorted(values)))
        self[hyperparameter_name]["values"] = values

        if set_mode_to_explicit:
            self._set_hyperparameter_mode_to_explicit(hyperparameter_name)

    def _set_numerical_range(self, hyperparameter_name, range_min=None, range_max=None, nb_values=None, set_mode_to_range=True):
        self._check_hyperparameter_name(hyperparameter_name)

        if range_min is None and range_max is None and nb_values is None:
            warnings.warn("Numerical range for hyperparameter \"{}\" not modified".format(hyperparameter_name))
        else:
            if range_min is not None:
                self._check_range_bound(hyperparameter_name, range_min)
                limit_min = self[hyperparameter_name]["limit"].get("min")
                if limit_min is not None:
                    assert limit_min <= range_min, "Range min {} is below hyperparameter \"{}\" limit {}".format(range_min, hyperparameter_name, limit_min)
            if range_max is not None:
                self._check_range_bound(hyperparameter_name, range_max)
                limit_max = self[hyperparameter_name]["limit"].get("max")
                if limit_max is not None:
                    assert range_max <= limit_max, "Range max {} is above hyperparameter \"{}\" limit {}".format(range_max, hyperparameter_name, limit_max)
            if nb_values is not None:
                assert isinstance(nb_values, int) and nb_values >= 2, "Range number of values for hyperparameter \"{}\" must be an integer and >= 2".format(hyperparameter_name)

            if range_min is not None:
                self[hyperparameter_name]["range"]["min"] = range_min
            if range_max is not None:
                self[hyperparameter_name]["range"]["max"] = range_max
            if nb_values is not None:
                self[hyperparameter_name]["range"]["nbValues"] = nb_values

        if set_mode_to_range:
            self._set_hyperparameter_mode_to_range(hyperparameter_name)

    def _set_categorical_values(self, hyperparameter_name, values=None):
        self._check_hyperparameter_name(hyperparameter_name)
        if values is None:
            warnings.warn("Categorical hyperparameter \"{}\" not modified".format(hyperparameter_name))
        else:
            assert isinstance(values, dict), "Invalid values input type for hyperparameter " \
                                             "\"{}\": ".format(hyperparameter_name) + \
                                             "must be a dictionary"
            admissible_values = self[hyperparameter_name]["values"].keys()
            for category, setting in values.items():
                assert category in admissible_values, "Unknown categorical value \"" + category + "\". Expected a member of " + str(list(admissible_values))
                value_error_message = "Invalid input value for hyperparameter \"{}\", category \"{}\": ".format(hyperparameter_name, category)
                value_error_message += "expected a {\"enabled\": bool} dictionary"
                assert isinstance(setting, dict), value_error_message
                assert list(setting.keys()) == ["enabled"], value_error_message
                assert list(type(v) for v in setting.values()) == [bool], value_error_message
            for category, setting in values.items():
                self[hyperparameter_name]["values"][category] = setting

    @property
    def strategy(self):
        return self._hyperparameter_search_params["strategy"]

    def _get_hyperparameter_mode(self, hyperparameter_name):
        if self.strategy == "GRID":
            return self[hyperparameter_name]["gridMode"]
        else:
            # RANDOM and BAYESIAN search strategies
            return self[hyperparameter_name]["randomMode"]

    def _check_hyperparameter_name(self, hyperparameter_name):
        assert is_basestring(hyperparameter_name), "Invalid type for hyperparameter name: expecting a string"
        hyperparameter_names = self._get_all_hyperparameter_names()
        if hyperparameter_name not in hyperparameter_names:
            message = "Unknown hyperparameter name: \"{}\". ".format(hyperparameter_name)
            message += "Expected a member of " + str(hyperparameter_names)
            raise ValueError(message)

    def _check_hyperparameter_searchable(self, hyperparameter_name):
        assert isinstance(self[hyperparameter_name], dict), "Hyperparameter \"{}\" cannot be searched".format(hyperparameter_name)

    def _check_hyperparameter_numerical(self, hyperparameter_name):
        assert "range" in self[hyperparameter_name], "Hyperparameter \"{}\" is not numerical".format(hyperparameter_name)

    def _check_range_bound(self, hyperparameter_name, range_bound):
        assert "range" in self[hyperparameter_name], "Cannot modify range of non-numerical hyperparameter " \
                                                         "\"{}\"".format(hyperparameter_name)
        assert isinstance(range_bound, int) or isinstance(range_bound, float), \
            "Invalid input type for hyperparameter \"{}\": ".format(hyperparameter_name) + \
            "range bounds must be numbers"


class RandomForestSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(RandomForestSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.n_estimators = NumericalHyperparameterSettings("n_estimators", self)
        self.min_samples_leaf = NumericalHyperparameterSettings("n_estimators", self)
        self.max_tree_depth = NumericalHyperparameterSettings("max_tree_depth", self)
        self.max_feature_prop = NumericalHyperparameterSettings("max_feature_prop", self)
        self.max_features = NumericalHyperparameterSettings("max_features", self)
        self.n_jobs = SingleValuedHyperparameterSettings("n_jobs", self, accepted_types=[int])
        self.selection_mode = SingleValuedHyperparameterSettings("selection_mode", self, accepted_values=["auto", "sqrt", "log2", "number","prop"])


class XGBoostSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(XGBoostSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.max_depth = NumericalHyperparameterSettings("max_depth", self)
        self.learning_rate = NumericalHyperparameterSettings("learning_rate", self)
        self.gamma = NumericalHyperparameterSettings("gamma", self)
        self.min_child_weight = NumericalHyperparameterSettings("min_child_weight", self)
        self.max_delta_step = NumericalHyperparameterSettings("max_delta_step", self)
        self.subsample = NumericalHyperparameterSettings("subsample", self)
        self.colsample_bytree = NumericalHyperparameterSettings("colsample_bytree", self)
        self.colsample_bylevel = NumericalHyperparameterSettings("colsample_bylevel", self)
        self.alpha = NumericalHyperparameterSettings("alpha", self)
        self.lambda_ = NumericalHyperparameterSettings("lambda", self)
        self.booster = CategoricalHyperparameterSettings("booster", self)
        self.objective = CategoricalHyperparameterSettings("objective", self)
        self.n_estimators = SingleValuedHyperparameterSettings("n_estimators", self, accepted_types=[int])
        self.nthread = SingleValuedHyperparameterSettings("nthread", self, accepted_types=[int])
        self.scale_pos_weight = SingleValuedHyperparameterSettings("scale_pos_weight", self, accepted_types=[int, float])
        self.base_score = SingleValuedHyperparameterSettings("base_score", self, accepted_types=[int, float])
        self.impute_missing = SingleValuedHyperparameterSettings("impute_missing", self, accepted_types=[bool])
        self.missing = SingleValuedHyperparameterSettings("missing", self, accepted_types=[int, float])
        self.cpu_tree_method = SingleValuedHyperparameterSettings("cpu_tree_method", self, accepted_values=["auto", "exact", "approx", "hist"])
        self.gpu_tree_method = SingleValuedHyperparameterSettings("gpu_tree_method", self, accepted_values=["gpu_exact", "gpu_hist"])
        self.enable_cuda = SingleValuedHyperparameterSettings("enable_cuda", self, accepted_types=[bool])
        self.seed = SingleValuedHyperparameterSettings("seed", self, accepted_types=[int])
        self.enable_early_stopping = SingleValuedHyperparameterSettings("enable_early_stopping", self, accepted_types=[bool])
        self.early_stopping_rounds = SingleValuedHyperparameterSettings("early_stopping_rounds", self, accepted_types=[int])


class GradientBoostedTreesSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(GradientBoostedTreesSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.n_estimators = NumericalHyperparameterSettings("n_estimator", self)
        self.max_depth = NumericalHyperparameterSettings("max_depth", self)
        self.min_samples_leaf = NumericalHyperparameterSettings("min_samples_leaf", self)
        self.max_features = NumericalHyperparameterSettings("max_features", self)
        self.max_feature_prop = NumericalHyperparameterSettings("max_feature_prop", self)
        self.learning_rate = NumericalHyperparameterSettings("learning_rate", self)
        self.loss = CategoricalHyperparameterSettings("loss", self)
        self.selection_mode = SingleValuedHyperparameterSettings("selection_mode", self, accepted_values=["auto", "sqrt", "log2", "number", "prop"])


class DecisionTreeSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(DecisionTreeSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.max_depth = NumericalHyperparameterSettings("max_depth", self)
        self.min_samples_leaf = NumericalHyperparameterSettings("min_samples_leaf", self)
        self.criterion = CategoricalHyperparameterSettings("criterion", self)
        self.splitter = CategoricalHyperparameterSettings("splitter", self)


class LogitSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(LogitSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.C = NumericalHyperparameterSettings("C", self)
        self.penalty = CategoricalHyperparameterSettings("penalty", self)
        self.multi_class = SingleValuedHyperparameterSettings("multi_class", self, accepted_values=["multinomial", "ovr"])
        self.n_jobs = SingleValuedHyperparameterSettings("n_jobs", self, accepted_types=[int])


class RidgeRegressionSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(RidgeRegressionSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.alpha = NumericalHyperparameterSettings("alpha", self)
        self.alpha_mode = SingleValuedHyperparameterSettings("alphaMode", self, accepted_values=["MANUAL", "AUTO"])


class LassoRegressionSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(LassoRegressionSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.alpha = NumericalHyperparameterSettings("alpha", self)
        self.alpha_mode = SingleValuedHyperparameterSettings("alphaMode", self, accepted_values=["MANUAL", "AUTO_CV", "AUTO_IC"]) # TODO: enforce attribute name = parameter name ?


class OLSSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(OLSSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.n_jobs = SingleValuedHyperparameterSettings("n_jobs", self, accepted_types=[int])


class LARSSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(LARSSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.max_features = SingleValuedHyperparameterSettings("max_features", self, accepted_types=[int])
        self.K = SingleValuedHyperparameterSettings("K", self, accepted_types=[int])


class SGDSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(SGDSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.alpha = NumericalHyperparameterSettings("alpha", self)
        self.loss = CategoricalHyperparameterSettings("loss", self)
        self.penalty = CategoricalHyperparameterSettings("penalty", self)
        self.l1_ratio = SingleValuedHyperparameterSettings("l1_ratio", self, accepted_types=[int, float])
        self.max_iter = SingleValuedHyperparameterSettings("max_iter", self, accepted_types=[int])
        self.tol = SingleValuedHyperparameterSettings("tol", self, accepted_types=[int, float])
        self.n_jobs = SingleValuedHyperparameterSettings("n_jobs", self, accepted_types=[int])


class KNNSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(KNNSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.k = NumericalHyperparameterSettings("k", self)
        self.algorithm = CategoricalHyperparameterSettings("algorithm", self)
        self.distance_weighting = SingleValuedHyperparameterSettings("distance_weighting", self, accepted_types=[bool])
        self.p = SingleValuedHyperparameterSettings("p", self, accepted_types=[int])
        self.leaf_size = SingleValuedHyperparameterSettings("leaf_size", self, accepted_types=[int])


class SVMSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(SVMSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.custom_gamma = NumericalHyperparameterSettings("custom_gamma", self)
        self.gamma = CategoricalHyperparameterSettings("gamma", self)
        self.kernel = CategoricalHyperparameterSettings("kernel", self)
        self.coef0 = SingleValuedHyperparameterSettings("coef0", self, accepted_types=[int, float])
        self.tol = SingleValuedHyperparameterSettings("tol", self, accepted_types=[int, float])
        self.max_iter = SingleValuedHyperparameterSettings("max_iter", self, accepted_types=[int])


class MLPSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(MLPSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.layer_sizes = NumericalHyperparameterSettings("layer_sizes", self)
        self.activation = SingleValuedHyperparameterSettings("activation", self, accepted_values=["relu", "identity", "logistic", "tanh"])
        self.solver = SingleValuedHyperparameterSettings("solver", self, accepted_values=["adam", "sgd"])
        self.alpha = SingleValuedHyperparameterSettings("alpha", self, accepted_types=[int, float])
        self.batch_size = SingleValuedHyperparameterSettings("batch_size", self, accepted_types=[int])
        self.auto_batch = SingleValuedHyperparameterSettings("auto_batch", self, accepted_types=[bool])
        self.max_iter = SingleValuedHyperparameterSettings("max_iter", self, accepted_types=[int])
        self.seed = SingleValuedHyperparameterSettings("seed", self, accepted_types=[int])
        self.tol = SingleValuedHyperparameterSettings("tol", self, accepted_types=[int, float])
        self.early_stopping = SingleValuedHyperparameterSettings("early_stopping", self, accepted_types=[bool])
        self.validation_fraction = SingleValuedHyperparameterSettings("validation_fraction", self, accepted_types=[int, float])
        self.beta_1 = SingleValuedHyperparameterSettings("beta_1", self, accepted_types=[int, float])
        self.beta_2 = SingleValuedHyperparameterSettings("beta_2", self, accepted_types=[int, float])
        self.epsilon = SingleValuedHyperparameterSettings("epsilon", self, accepted_types=[int, float])
        self.learning_rate = SingleValuedHyperparameterSettings("learning_rate", self, accepted_values=["constant", "invscaling", "adaptive"])
        self.power_t = SingleValuedHyperparameterSettings("power_t", self, accepted_types=[int, float])
        self.momentum = SingleValuedHyperparameterSettings("momentum", self, accepted_types=[int, float])
        self.nesterovs_momentum = SingleValuedHyperparameterSettings("nesterovs_momentum", self, accepted_types=[bool])
        self.shuffle = SingleValuedHyperparameterSettings("shuffle", self, accepted_types=[bool])
        self.learning_rate_init = SingleValuedHyperparameterSettings("learning_rate_init", self, accepted_types=[int, float])


class MLLibLogitSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(MLLibLogitSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.reg_param = NumericalHyperparameterSettings("reg_param", self)
        self.enet_param = NumericalHyperparameterSettings("enet_param", self)
        self.max_iter = SingleValuedHyperparameterSettings("max_iter", self, accepted_types=[int])


class MLLibNaiveBayesSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(MLLibNaiveBayesSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.lambda_ = NumericalHyperparameterSettings("lambda", self)


class MLLibLinearRegressionSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(MLLibLinearRegressionSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.reg_param = NumericalHyperparameterSettings("reg_param", self)
        self.enet_param = NumericalHyperparameterSettings("enet_param", self)
        self.max_iter = SingleValuedHyperparameterSettings("max_iter", self, accepted_types=[int])


class MLLibDecisionTreeSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(MLLibDecisionTreeSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.max_depth = NumericalHyperparameterSettings("max_depth", self)
        self.cache_node_ids = SingleValuedHyperparameterSettings("cache_node_ids", self, accepted_types=[bool])
        self.checkpoint_interval = SingleValuedHyperparameterSettings("checkpoint_interval", self, accepted_types=[int])
        self.max_bins = SingleValuedHyperparameterSettings("max_bins", self, accepted_types=[int])
        self.max_memory_mb = SingleValuedHyperparameterSettings("max_memory_mb", self, accepted_types=[int])
        self.min_info_gain = SingleValuedHyperparameterSettings("min_info_gain", self, accepted_types=[int, float])
        self.min_instance_per_node = SingleValuedHyperparameterSettings("min_instance_per_node", self, accepted_types=[int])


class _MLLibTreeEnsembleSettings(AlgorithmSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(_MLLibTreeEnsembleSettings, self).__init__(raw_settings, hyperparameter_search_params)

        self.max_depth = NumericalHyperparameterSettings("max_depth", self)
        self.num_trees = NumericalHyperparameterSettings("num_trees", self)

        self.cache_node_ids = SingleValuedHyperparameterSettings("cache_node_ids", self, accepted_types=[bool])
        self.checkpoint_interval = SingleValuedHyperparameterSettings("checkpoint_interval", self, accepted_types=[int])
        self.impurity = SingleValuedHyperparameterSettings("impurity", self, accepted_values=["gini", "entropy", "variance"])  # TODO: distinguish between regression and classif
        self.max_bins = SingleValuedHyperparameterSettings("max_bins", self, accepted_types=[int])
        self.max_memory_mb = SingleValuedHyperparameterSettings("max_memory_mb", self, accepted_types=[int])
        self.min_info_gain = SingleValuedHyperparameterSettings("min_info_gain", self, accepted_types=[int, float])
        self.min_instance_per_node = SingleValuedHyperparameterSettings("min_instance_per_node", self, accepted_types=[int])
        self.seed = SingleValuedHyperparameterSettings("seed", self, accepted_types=[int])
        self.subsampling_rate = SingleValuedHyperparameterSettings("subsampling_rate", self, accepted_types=[int, float])


class MLLibRandomForestSettings(_MLLibTreeEnsembleSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(MLLibRandomForestSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.impurity = SingleValuedHyperparameterSettings("impurity", self, accepted_values=["gini", "entropy", "variance"])
        self.subset_strategy = SingleValuedHyperparameterSettings("subset_strategy", self, accepted_values=["auto", "all", "onethird", "sqrt", "log2"])


class MLLibGBTSettings(_MLLibTreeEnsembleSettings):

    def __init__(self, raw_settings, hyperparameter_search_params):
        super(MLLibGBTSettings, self).__init__(raw_settings, hyperparameter_search_params)
        self.step_size = NumericalHyperparameterSettings("step_size", self)


class AlgorithmMeta:
    def __init__(self, algorithm_name, algorithm_settings_class=AlgorithmSettings):
        self.algorithm_name = algorithm_name
        self.algorithm_settings_class = algorithm_settings_class


class DSSPredictionMLTaskSettings(DSSMLTaskSettings):
    __doc__ = []
    algorithm_remap = {
            "RANDOM_FOREST_CLASSIFICATION": AlgorithmMeta("random_forest_classification", RandomForestSettings),
            "RANDOM_FOREST_REGRESSION": AlgorithmMeta("random_forest_regression", RandomForestSettings),
            "EXTRA_TREES": AlgorithmMeta("extra_trees", RandomForestSettings),
            "GBT_CLASSIFICATION": AlgorithmMeta("gbt_classification", GradientBoostedTreesSettings),
            "GBT_REGRESSION": AlgorithmMeta("gbt_regression", GradientBoostedTreesSettings),
            "DECISION_TREE_CLASSIFICATION": AlgorithmMeta("decision_tree_classification", DecisionTreeSettings),
            "DECISION_TREE_REGRESSION": AlgorithmMeta("decision_tree_regression", DecisionTreeSettings),
            "RIDGE_REGRESSION": AlgorithmMeta("ridge_regression", RidgeRegressionSettings),
            "LASSO_REGRESSION": AlgorithmMeta("lasso_regression", LassoRegressionSettings),
            "LEASTSQUARE_REGRESSION": AlgorithmMeta("leastsquare_regression", OLSSettings),
            "SGD_REGRESSION": AlgorithmMeta("sgd_regression", SGDSettings),
            "KNN": AlgorithmMeta("knn", KNNSettings),
            "LOGISTIC_REGRESSION": AlgorithmMeta("logistic_regression", LogitSettings),
            "NEURAL_NETWORK": AlgorithmMeta("neural_network", MLPSettings),
            "SVC_CLASSIFICATION": AlgorithmMeta("svc_classifier", SVMSettings),
            "SVM_REGRESSION": AlgorithmMeta("svm_regression", SVMSettings),
            "SGD_CLASSIFICATION": AlgorithmMeta("sgd_classifier", SGDSettings),
            "LARS": AlgorithmMeta("lars_params", LARSSettings),
            "XGBOOST_CLASSIFICATION": AlgorithmMeta("xgboost", XGBoostSettings),
            "XGBOOST_REGRESSION": AlgorithmMeta("xgboost", XGBoostSettings),
            "SPARKLING_DEEP_LEARNING": AlgorithmMeta("deep_learning_sparkling"),
            "SPARKLING_GBM": AlgorithmMeta("gbm_sparkling"),
            "SPARKLING_RF": AlgorithmMeta("rf_sparkling"),
            "SPARKLING_GLM": AlgorithmMeta("glm_sparkling"),
            "SPARKLING_NB": AlgorithmMeta("nb_sparkling"),
            "MLLIB_LOGISTIC_REGRESSION": AlgorithmMeta("mllib_logit", MLLibLogitSettings),
            "MLLIB_NAIVE_BAYES": AlgorithmMeta("mllib_naive_bayes", MLLibNaiveBayesSettings),
            "MLLIB_LINEAR_REGRESSION": AlgorithmMeta("mllib_linreg", MLLibLinearRegressionSettings),
            "MLLIB_RANDOM_FOREST": AlgorithmMeta("mllib_rf", MLLibRandomForestSettings),
            "MLLIB_GBT": AlgorithmMeta("mllib_gbt", MLLibGBTSettings),
            "MLLIB_DECISION_TREE": AlgorithmMeta("mllib_dt", MLLibDecisionTreeSettings),
            "VERTICA_LINEAR_REGRESSION": AlgorithmMeta("vertica_linear_regression"),
            "VERTICA_LOGISTIC_REGRESSION": AlgorithmMeta("vertica_logistic_regression"),
            "KERAS_CODE": AlgorithmMeta("keras")
        }

    class PredictionTypes:
        BINARY = "BINARY_CLASSIFICATION"
        REGRESSION = "REGRESSION"
        MULTICLASS = "MULTICLASS"

    def __init__(self, client, project_key, analysis_id, mltask_id, mltask_settings):
        DSSMLTaskSettings.__init__(self, client, project_key, analysis_id, mltask_id, mltask_settings)

        if self.get_prediction_type() not in [self.PredictionTypes.BINARY, self.PredictionTypes.REGRESSION, self.PredictionTypes.MULTICLASS]:
            raise ValueError("Unknown prediction type: {}".format(self.prediction_type))

        self.classification_prediction_types = [self.PredictionTypes.BINARY, self.PredictionTypes.MULTICLASS]

    def get_prediction_type(self):
        return self.mltask_settings['predictionType']

    @property
    def split_params(self):
        """
        Gets a handle to modify train/test splitting params.

        :rtype: :class:`PredictionSplitParamsHandler`
        """
        return self.get_split_params()

    def get_split_params(self):
        """
        Gets a handle to modify train/test splitting params.
        
        :rtype: :class:`PredictionSplitParamsHandler`
        """
        return PredictionSplitParamsHandler(self.mltask_settings)

    def split_ordered_by(self, feature_name, ascending=True):
        """
        Deprecated. Use split_params.set_time_ordering()
        """
        warnings.warn("split_ordered_by() is deprecated, please use split_params.set_time_ordering() instead", DeprecationWarning)
        self.split_params.set_time_ordering(feature_name, ascending=ascending)

        return self

    def remove_ordered_split(self):
        """
        Deprecated. Use split_params.unset_time_ordering()
        """
        warnings.warn("remove_ordered_split() is deprecated, please use split_params.unset_time_ordering() instead", DeprecationWarning)
        self.split_params.unset_time_ordering()

        return self

    def use_sample_weighting(self, feature_name):
        """
        Deprecated. use set_weighting()
        """
        warnings.warn("use_sample_weighting() is deprecated, please use set_weighting() instead", DeprecationWarning)
        return self.set_weighting(method='SAMPLE_WEIGHT', feature_name=feature_name, )

    def set_weighting(self, method, feature_name=None):
        """
        Sets the method to weight samples. 

        If there was a WEIGHT feature declared previously, it will be set back as an INPUT feature first.

        :param str method: Method to use. One of NO_WEIGHTING, SAMPLE_WEIGHT (must give a feature name),
                        CLASS_WEIGHT or CLASS_AND_SAMPLE_WEIGHT (must give a feature name)
        :param str feature_name: Name of the feature to use as sample weight
        """

        # First, if there was a WEIGHT feature, restore it as INPUT
        for other_feature_name in self.mltask_settings['preprocessing']['per_feature']:
            if self.mltask_settings['preprocessing']['per_feature'][other_feature_name]['role'] == 'WEIGHT':
                self.mltask_settings['preprocessing']['per_feature'][other_feature_name]['role'] = 'INPUT'

        if method == "NO_WEIGHTING":
            self.mltask_settings['weight']['weightMethod'] = method

        elif method == "SAMPLE_WEIGHT":
            if not feature_name in self.mltask_settings["preprocessing"]["per_feature"]:
                raise ValueError("Feature %s doesn't exist in this ML task, can't use as weight" % feature_name)

            self.mltask_settings['weight']['weightMethod'] = method
            self.mltask_settings['weight']['sampleWeightVariable'] = feature_name
            self.mltask_settings['preprocessing']['per_feature'][feature_name]['role'] = 'WEIGHT'

        elif method == "CLASS_WEIGHT":
            if self.get_prediction_type() not in self.classification_prediction_types:
                raise ValueError("Weighting method: {} not compatible with prediction type: {}, should be in {}".format(method, self.get_prediction_type(), self.classification_prediction_types))

            self.mltask_settings['weight']['weightMethod'] = method

        elif method == "CLASS_AND_SAMPLE_WEIGHT":
            if self.get_prediction_type() not in self.classification_prediction_types:
                raise ValueError("Weighting method: {} not compatible with prediction type: {}, should be in {}".format(method, self.get_prediction_type(), self.classification_prediction_types))
            if not feature_name in self.mltask_settings["preprocessing"]["per_feature"]:
                raise ValueError("Feature %s doesn't exist in this ML task, can't use as weight" % feature_name)
            
            self.mltask_settings['weight']['weightMethod'] = method
            self.mltask_settings['weight']['sampleWeightVariable'] = feature_name
            self.mltask_settings['preprocessing']['per_feature'][feature_name]['role'] = 'WEIGHT'

        else:
            raise ValueError("Unknown weighting method: {}".format(method))

        return self

    def remove_sample_weighting(self):
        """
        Deprecated. Use set_weighting(method=\"NO_WEIGHTING\") instead
        """
        warnings.warn("remove_sample_weighting() is deprecated, please use set_weighting(method=\"NO_WEIGHTING\") instead", DeprecationWarning)
        return self.set_weighting(method="NO_WEIGHTING")


class DSSClusteringMLTaskSettings(DSSMLTaskSettings):
    __doc__ = []
    algorithm_remap = {
            "DBSCAN" : "db_scan_clustering",
        }



class DSSTrainedModelDetails(object):
    def __init__(self, details, snippet, saved_model=None, saved_model_version=None, mltask=None, mltask_model_id=None):
        self.details = details
        self.snippet = snippet
        self.saved_model = saved_model
        self.saved_model_version = saved_model_version
        self.mltask = mltask
        self.mltask_model_id = mltask_model_id

    def get_raw(self):
        """
        Gets the raw dictionary of trained model details
        """
        return self.details

    def get_raw_snippet(self):
        """
        Gets the raw dictionary of trained model snippet. 
        The snippet is a lighter version than the details.
        """
        return self.snippet

    def get_train_info(self):
        """
        Returns various information about the train process (size of the train set, quick description, timing information)

        :rtype: dict
        """
        return self.details["trainInfo"]

    def get_user_meta(self):
        """
        Gets the user-accessible metadata (name, description, cluster labels, classification threshold)
        Returns the original object, not a copy. Changes to the returned object are persisted to DSS by calling
        :meth:`save_user_meta`

        """
        return self.details["userMeta"]

    def save_user_meta(self):
        um = self.details["userMeta"]

        if self.mltask is not None:
            self.mltask.client._perform_empty(
                "PUT", "/projects/%s/models/lab/%s/%s/models/%s/user-meta" % (self.mltask.project_key,
                    self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id), body = um)
        else:
            self.saved_model.client._perform_empty(
                "PUT", "/projects/%s/savedmodels/%s/versions/%s/user-meta" % (self.saved_model.project_key,
                    self.saved_model.sm_id, self.saved_model_version), body = um)

    def get_origin_analysis_trained_model(self):
        """
        Fetch details about the model in an analysis, this model has been exported from. Returns None if the
        deployed trained model does not have an origin analysis trained model.

        :rtype: DSSTrainedModelDetails | None
        """
        if self.saved_model is None:
            return self
        else:
            fmi = self.get_raw().get("smOrigin", {}).get("fullModelId")
            if fmi is not None:
                origin_ml_task = DSSMLTask.from_full_model_id(self.saved_model.client, fmi,
                                                              project_key=self.saved_model.project_key)
                return origin_ml_task.get_trained_model_details(fmi)

class DSSTreeNode(object):
    def __init__(self, tree, i):
        self.tree = tree
        self.i = i

    def get_left_child(self):
        """Gets a :class:`dataikuapi.dss.ml.DSSTreeNode` representing the left side of the tree node (or None)"""
        left = self.tree.tree['leftChild'][self.i]
        if left < 0:
            return None
        else:
            return DSSTreeNode(self.tree, left)

    def get_right_child(self):
        """Gets a :class:`dataikuapi.dss.ml.DSSTreeNode` representing the right side of the tree node (or None)"""
        left = self.tree.tree['rightChild'][self.i]
        if left < 0:
            return None
        else:
            return DSSTreeNode(self.tree, left)

    def get_split_info(self):
        """Gets the information on the split, as a dict"""
        info = {}
        features = self.tree.tree.get("feature", None)
        probas = self.tree.tree.get("probas", None)
        leftCategories = self.tree.tree.get("leftCategories", None)
        impurities = self.tree.tree.get("impurity", None)
        predicts = self.tree.tree.get("predict", None)
        thresholds = self.tree.tree.get("threshold", None)
        nSamples = self.tree.tree.get("nSamples", None)
        info['feature'] = self.tree.feature_names[features[self.i]] if features is not None else None
        info['probas'] = probas[self.i] if probas is not None else None
        info['leftCategories'] = leftCategories[self.i] if leftCategories is not None else None
        info['impurity'] = impurities[self.i] if impurities is not None else None
        info['predict'] = predicts[self.i] if predicts is not None else None
        info['nSamples'] = nSamples[self.i] if nSamples is not None else None
        info['threshold'] = thresholds[self.i] if thresholds is not None else None
        return info

class DSSTree(object):
    def __init__(self, tree, feature_names):
        self.tree = tree
        self.feature_names = feature_names

    def get_raw(self):
        """Gets the raw tree data structure"""
        return self.tree

    def get_root(self):
        """Gets a :class:`dataikuapi.dss.ml.DSSTreeNode` representing the root of the tree"""
        return DSSTreeNode(self, 0)

class DSSTreeSet(object):
    def __init__(self, trees):
        self.trees = trees

    def get_raw(self):
        """Gets the raw trees data structure"""
        return self.trees

    def get_feature_names(self):
        """Gets the list of feature names (after dummification) """
        return self.trees["featureNames"]

    def get_trees(self):
        """Gets the list of trees as :class:`dataikuapi.dss.ml.DSSTree` """
        return [DSSTree(t, self.trees["featureNames"]) for t in self.trees["trees"]]

class DSSCoefficientPaths(object):
    def __init__(self, paths):
        self.paths = paths

    def get_raw(self):
        """Gets the raw paths data structure"""
        return self.paths

    def get_feature_names(self):
        """Get the feature names (after dummification)"""
        return self.paths['features']

    def get_coefficient_path(self, feature, class_index=0):
        """Get the path of the feature"""
        i = self.paths['features'].index(feature)
        if i >= 0 and i < len(self.paths['path'][0][class_index]):
            n = len(self.paths['path'])
            return [self.paths['path'][j][class_index][i] for j in range(0, n)]
        else:
            return None

class DSSScatterPlots(object):
    def __init__(self, scatters):
        self.scatters = scatters

    def get_raw(self):
        """Gets the raw scatters data structure"""
        return self.scatters

    def get_feature_names(self):
        """Get the feature names (after dummification)"""
        feature_names = []
        for k in self.scatters['features']:
            feature_names.append(k)
        return feature_names

    def get_scatter_plot(self, feature_x, feature_y):
        """Get the scatter plot between feature_x and feature_y"""
        ret = {'cluster':self.scatters['cluster'], 'x':self.scatters['features'].get(feature_x, None), 'y':self.scatters['features'].get(feature_x, None)}
        return ret

class DSSTrainedPredictionModelDetails(DSSTrainedModelDetails):
    """
    Object to read details of a trained prediction model

    Do not create this object directly, use :meth:`DSSMLTask.get_trained_model_details()` instead
    """

    def __init__(self, details, snippet, saved_model=None, saved_model_version=None, mltask=None, mltask_model_id=None):
        DSSTrainedModelDetails.__init__(self, details, snippet, saved_model, saved_model_version, mltask, mltask_model_id)

    def get_roc_curve_data(self):
        roc = self.details.get("perf", {}).get("rocVizData",{})
        if roc is None:
            raise ValueError("This model does not have ROC visualization data")

        return roc

    def get_performance_metrics(self):
        """
        Returns all performance metrics for this model.

        For binary classification model, this includes both "threshold-independent" metrics like AUC and
        "threshold-dependent" metrics like precision. Threshold-dependent metrics are returned at the
        threshold value that was found to be optimal during training.

        To get access to the per-threshold values, use the following:

        .. code-block:: python

            # Returns a list of tested threshold values
            details.get_performance()["perCutData"]["cut"]
            # Returns a list of F1 scores at the tested threshold values
            details.get_performance()["perCutData"]["f1"]
            # Both lists have the same length

        If K-Fold cross-test was used, most metrics will have a "std" variant, which is the standard deviation
        accross the K cross-tested folds. For example, "auc" will be accompanied with "aucstd"

        :returns: a dict of performance metrics values
        :rtype: dict
        """
        import copy
        clean_snippet = copy.deepcopy(self.snippet)
        for x in ["gridsearchData", "trainDate", "topImportance", "backendType", "userMeta", "sessionDate", "trainInfo", "fullModelId", "gridLength", "algorithm", "sessionId"]:
            if x in clean_snippet:
                del clean_snippet[x]
        return clean_snippet


    def get_hyperparameter_search_points(self):
        """
        Gets the list of points in the hyperparameter search space that have been tested.

        Returns a list of dict. Each entry in the list represents a point.

        For each point, the dict contains at least:
            - "score": the average value of the optimization metric over all the folds at this point
            - "params": a dict of the parameters at this point. This dict has the same structure 
               as the params of the best parameters
        """

        if not "gridCells" in self.details["iperf"]:
            raise ValueError("No hyperparameter search result, maybe this model did not perform hyperparameter optimization")
        return self.details["iperf"]["gridCells"]

    def get_preprocessing_settings(self):
        """
        Gets the preprocessing settings that were used to train this model

        :rtype: dict
        """
        return self.details["preprocessing"]

    def get_modeling_settings(self):
        """
        Gets the modeling (algorithms) settings that were used to train this model.

        Note: the structure of this dict is not the same as the modeling params on the ML Task
        (which may contain several algorithm)

        :rtype: dict
        """
        return self.details["modeling"]

    def get_actual_modeling_params(self):
        """
        Gets the actual / resolved parameters that were used to train this model, post
        hyperparameter optimization.

        :return: A dictionary, which contains at least a "resolved" key, which is a dict containing the post-optimization parameters
        :rtype: dict
        """
        return self.details["actualParams"]

    def get_trees(self):
        """
        Gets the trees in the model (for tree-based models) 

        :return: a DSSTreeSet object to interact with the trees
        :rtype: :class:`dataikuapi.dss.ml.DSSTreeSet`
        """
        data = self.mltask.client._perform_json(
            "GET", "/projects/%s/models/lab/%s/%s/models/%s/trees" % (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id))
        if data is None:
            raise ValueError("This model has no tree data")
        return DSSTreeSet(data)

    def get_coefficient_paths(self):
        """
        Gets the coefficient paths for Lasso models

        :return: a DSSCoefficientPaths object to interact with the coefficient paths
        :rtype: :class:`dataikuapi.dss.ml.DSSCoefficientPaths`
        """
        data = self.mltask.client._perform_json(
            "GET", "/projects/%s/models/lab/%s/%s/models/%s/coef-paths" % (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id))
        if data is None:
            raise ValueError("This model has no coefficient paths")
        return DSSCoefficientPaths(data)

    ## Model export

    def get_scoring_jar_stream(self, model_class="model.Model", include_libs=False):
        """
        Get a scoring jar for this trained model,
        provided that you have the license to do so and that the model is compatible with optimized scoring.
        You need to close the stream after download. Failure to do so will result in the DSSClient becoming unusable.

        :param str  model_class: fully-qualified class name, e.g. "com.company.project.Model"
        :param bool include_libs: if True, also packs the required dependencies;
                if False, runtime will require the scoring libs given by :func:`DSSClient.scoring_libs`
        :returns: a jar file, as a stream
        :rtype: file-like
        """
        include_libs = "true" if include_libs else "false"
        if self.mltask is not None:
            return self.mltask.client._perform_raw(
                "GET", "/projects/%s/models/lab/%s/%s/models/%s/scoring-jar?fullClassName=%s&includeLibs=%s" %
                (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id,
                model_class, include_libs))
        else:
            return self.saved_model.client._perform_raw(
                "GET", "/projects/%s/savedmodels/%s/versions/%s/scoring-jar?fullClassName=%s&includeLibs=%s" %
                (self.saved_model.project_key, self.saved_model.sm_id, self.saved_model_version,
                model_class, include_libs))

    def get_scoring_pmml_stream(self):
        """
        Get a scoring PMML for this trained model,
        provided that you have the license to do so and that the model is compatible with PMML scoring
        You need to close the stream after download. Failure to do so will result in the DSSClient becoming unusable.

        :returns: a PMML file, as a stream
        :rtype: file-like
        """
        if self.mltask is not None:
            return self.mltask.client._perform_raw(
                "GET", "/projects/%s/models/lab/%s/%s/models/%s/scoring-pmml" %
                (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id))
        else:
            return self.saved_model.client._perform_raw(
                "GET", "/projects/%s/savedmodels/%s/versions/%s/scoring-pmml" %
                (self.saved_model.project_key, self.saved_model.sm_id, self.saved_model_version))

    ## Post-train computations

    def compute_subpopulation_analyses(self, split_by, wait=True, sample_size=1000, random_state=1337, n_jobs=1, debug_mode=False):
        """
        Launch computation of Subpopulation analyses for this trained model.

        :param list|str split_by: column(s) on which subpopulation analyses are to be computed (one analysis per column)
        :param bool wait: if True, the call blocks until the computation is finished and returns the results directly
        :param int sample_size: number of records of the dataset to use for the computation 
        :param int random_state: random state to use to build sample, for reproducibility
        :param int n_jobs: number of cores used for parallel training. (-1 means 'all cores')
        :param bool debug_mode: if True, output all logs (slower)

        :returns: if wait is True, an object containing the Subpopulation analyses, else a future to wait on the result
        :rtype: :class:`dataikuapi.dss.ml.DSSSubpopulationAnalyses` or :class:`dataikuapi.dss.future.DSSFuture`
        """
        body = {
            "features": split_by if isinstance(split_by, list) else [split_by],
            "computationParams": {
                "sample_size": sample_size,
                "random_state": random_state,
                "n_jobs": n_jobs,
                "debug_mode": debug_mode,
            }}
        if self.mltask is not None:
            future_response = self.mltask.client._perform_json(
                "POST", "/projects/%s/models/lab/%s/%s/models/%s/subpopulation-analyses" %
                (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id),
                body=body
            )
            future = DSSFuture(self.mltask.client, future_response.get("jobId", None), future_response)
        else:
            future_response = self.saved_model.client._perform_json(
                "POST", "/projects/%s/savedmodels/%s/versions/%s/subpopulation-analyses" %
                (self.saved_model.project_key, self.saved_model.sm_id, self.saved_model_version),
                body=body
            )
            future = DSSFuture(self.saved_model.client, future_response.get("jobId", None), future_response)
        if wait:
            prediction_type = self.details.get("coreParams", {}).get("prediction_type")
            return DSSSubpopulationAnalyses(future.wait_for_result(), prediction_type)
        else:
            return future


    def get_subpopulation_analyses(self):
        """
        Retrieve all subpopulation analyses computed for this trained model
        
        :returns: the subpopulation analyses
        :rtype: :class:`dataikuapi.dss.ml.DSSSubpopulationAnalyses`
        """
        
        if self.mltask is not None:
            data = self.mltask.client._perform_json(
                "GET", "/projects/%s/models/lab/%s/%s/models/%s/subpopulation-analyses" %
                (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id)
            )
        else:
            data = self.saved_model.client._perform_json(
                "GET", "/projects/%s/savedmodels/%s/versions/%s/subpopulation-analyses" %
                (self.saved_model.project_key, self.saved_model.sm_id, self.saved_model_version),
            )
        prediction_type = self.details.get("coreParams", {}).get("prediction_type")
        return DSSSubpopulationAnalyses(data, prediction_type)

    def compute_partial_dependencies(self, features, wait=True, sample_size=1000, random_state=1337, n_jobs=1, debug_mode=False):
        """
        Launch computation of Partial dependencies for this trained model.

        :param list|str features: feature(s) on which partial dependencies are to be computed
        :param bool wait: if True, the call blocks until the computation is finished and returns the results directly
        :param int sample_size: number of records of the dataset to use for the computation 
        :param int random_state: random state to use to build sample, for reproducibility
        :param int n_jobs: number of cores used for parallel training. (-1 means 'all cores')
        :param bool debug_mode: if True, output all logs (slower)

        :returns: if wait is True, an object containing the Partial dependencies, else a future to wait on the result
        :rtype: :class:`dataikuapi.dss.ml.DSSPartialDependencies` or :class:`dataikuapi.dss.future.DSSFuture`
        """

        body = {
            "features": features if isinstance(features, list) else [features],
            "computationParams": {
                "sample_size": sample_size,
                "random_state": random_state,
                "n_jobs": n_jobs,
                "debug_mode": debug_mode,
            }}
        if self.mltask is not None:
            future_response = self.mltask.client._perform_json(
                "POST", "/projects/%s/models/lab/%s/%s/models/%s/partial-dependencies" %
                (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id),
                body=body
            )
            future = DSSFuture(self.mltask.client, future_response.get("jobId", None), future_response)
        else:
            future_response = self.saved_model.client._perform_json(
                "POST", "/projects/%s/savedmodels/%s/versions/%s/partial-dependencies" %
                (self.saved_model.project_key, self.saved_model.sm_id, self.saved_model_version),
                body=body
            )
            future = DSSFuture(self.saved_model.client, future_response.get("jobId", None), future_response)
        if wait:
            return DSSPartialDependencies(future.wait_for_result()) 
        else:
            return future

    def get_partial_dependencies(self):
        """
        Retrieve all partial dependencies computed for this trained model

        :returns: the partial dependencies
        :rtype: :class:`dataikuapi.dss.ml.DSSPartialDependencies`
        """

        if self.mltask is not None:
            data = self.mltask.client._perform_json(
                "GET", "/projects/%s/models/lab/%s/%s/models/%s/partial-dependencies" %
                (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id)
            )
        else:
            data = self.saved_model.client._perform_json(
                "GET", "/projects/%s/savedmodels/%s/versions/%s/partial-dependencies" %
                (self.saved_model.project_key, self.saved_model.sm_id, self.saved_model_version),
            )
        return DSSPartialDependencies(data)


class DSSSubpopulationGlobal(object):
    """
    Object to read details of performance on global population used for subpopulation analyses.

    Do not create this object directly, use :meth:`DSSSubpopulationAnalyses.get_global()` instead
    """

    def __init__(self, data, prediction_type):
        self._internal_dict = data
        self.prediction_type = prediction_type

    def get_raw(self):
        """
        Gets the raw dictionary of the global subpopulation performance

        :rtype: dict
        """
        return self._internal_dict

    def __repr__(self):
        return "{cls}(prediction_type={type})".format(cls=self.__class__.__name__, type=self.prediction_type)

    def get_performance_metrics(self):
        """
        Gets the performance results of the global population used for the subpopulation analysis
        """
        return self._internal_dict["performanceMetrics"]

    def get_prediction_info(self):
        """
        Gets the prediction info of the global population used for the subpopulation analysis
        """
        global_metrics = self._internal_dict["perf"]["globalMetrics"]
        if self.prediction_type == "BINARY_CLASSIFICATION":
            return {
                "predictedPositiveRatio": global_metrics["predictionAvg"][0],
                "actualPositiveRatio": global_metrics["targetAvg"][0],
                "testWeight": global_metrics["testWeight"]
            }
        elif self.prediction_type == "REGRESSION":
            return {
                "predictedAvg":global_metrics["predictionAvg"][0],
                "predictedStd":global_metrics["predictionStd"][0],
                "actualAvg":global_metrics["targetAvg"][0],
                "actualStd":global_metrics["targetStd"][0],
                "testWeight":global_metrics["testWeight"]
            }


class DSSSubpopulationModality(object):
    """
    Object to read details of a subpopulation analysis modality

    Do not create this object directly, use :meth:`DSSSubpopulationAnalysis.get_modality_data(definition)` instead
    """

    def __init__(self, feature_name, computed_as_type, data, prediction_type):
        self._internal_dict = data
        self.prediction_type = prediction_type
        if computed_as_type == "CATEGORY":
            self.definition = DSSSubpopulationCategoryModalityDefinition(feature_name, data)
        elif computed_as_type == "NUMERIC":
            self.definition = DSSSubpopulationNumericModalityDefinition(feature_name, data)

    def get_raw(self):
        """
        Gets the raw dictionary of the subpopulation analysis modality

        :rtype: dict
        """
        return self._internal_dict

    def __repr__(self):
        computed_as_type = "CATEGORY" if isinstance(self.definition, DSSSubpopulationCategoryModalityDefinition) else 'NUMERIC'
        return "{cls}(prediction_type={type}, feature={feature}, computed_as={computed_as_type})".format(
            cls=self.__class__.__name__,
            type=self.prediction_type,
            feature=self.definition.feature_name,
            computed_as_type=computed_as_type)

    def get_definition(self):
        """
        Gets the definition of the subpopulation analysis modality

        :returns: definition
        :rtype: :class:`dataikuapi.dss.ml.DSSSubpopulationModalityDefinition`
        """
        return self.definition
    
    def is_excluded(self):
        """
        Whether modality has been excluded from analysis (e.g. too few rows in the subpopulation)
        """
        return self._internal_dict.get("excluded", False)

    def get_performance_metrics(self):
        """
        Gets the performance results of the modality
        """
        if self.is_excluded():
            raise ValueError("Excluded modalities do not have performance metrics")
        return self._internal_dict["performanceMetrics"]

    def get_prediction_info(self):
        """
        Gets the prediction info of the modality
        """
        if self.is_excluded():
            raise ValueError("Excluded modalities do not have prediction info")
        global_metrics = self._internal_dict["perf"]["globalMetrics"]
        if self.prediction_type == "BINARY_CLASSIFICATION":
            return {
                "predictedPositiveRatio": global_metrics["predictionAvg"][0],
                "actualPositiveRatio": global_metrics["targetAvg"][0],
                "testWeight": global_metrics["testWeight"]
            }
        elif self.prediction_type == "REGRESSION":
            return {
                "predictedAvg":global_metrics["predictionAvg"][0],
                "predictedStd":global_metrics["predictionStd"][0],
                "actualAvg":global_metrics["targetAvg"][0],
                "actualStd":global_metrics["targetStd"][0],
                "testWeight":global_metrics["testWeight"]
            }


class DSSSubpopulationModalityDefinition(object):

    MISSING_VALUES = "__DSSSubpopulationModalidityDefinition__MISSINGVALUES"

    def __init__(self, feature_name, data):
        self.missing_values = data.get("missing_values", False)
        self.index = data.get("index")
        self.feature_name = feature_name
    
    def is_missing_values(self):
        return self.missing_values


class DSSSubpopulationNumericModalityDefinition(DSSSubpopulationModalityDefinition):
    
    def __init__(self, feature_name, data):
        super(DSSSubpopulationNumericModalityDefinition, self).__init__(feature_name, data)
        self.lte = data.get("lte", None)
        self.gt = data.get("gt", None)
        self.gte = data.get("gte", None)
    
    def contains(self, value):
        lte = self.lte if self.lte is not None else float("inf")
        gt = self.gt if self.gt is not None else float("-inf")
        gte = self.gte if self.gte is not None else float("-inf")
        return not self.missing_values and gt < value and gte <= value and lte >= value
    
    def __repr__(self):
        if self.missing_values:
            return "DSSSubpopulationNumericModalityDefinition(missing_values)"
        else:
            if self.gt is not None:
                repr_gt = "%s<" % self.gt
            elif self.gte is not None:
                repr_gt = "%s<=" % self.gte
            else:
                repr_gt = ""

            if self.lte is not None:
                repr_lt = "<=%s" % self.lte
            else:
                repr_lt = ""

            return "DSSSubpopulationNumericModalityDefinition(%s%s%s)" % (repr_gt, self.feature_name, repr_lt)

class DSSSubpopulationCategoryModalityDefinition(DSSSubpopulationModalityDefinition):

    def __init__(self, feature_name, data):
        super(DSSSubpopulationCategoryModalityDefinition, self).__init__(feature_name, data)
        self.value = data.get("value", None)
    
    def contains(self, value):
        return value == self.value

    def __repr__(self):
        if self.missing_values:
            return "DSSSubpopulationCategoryModalityDefinition(missing_values)"
        else:
            return "DSSSubpopulationCategoryModalityDefinition(%s='%s')" % (self.feature_name, self.value)


class DSSSubpopulationAnalysis(object):
    """
    Object to read details of a subpopulation analysis of a trained model

    Do not create this object directly, use :meth:`DSSSubpopulationAnalyses.get_analysis(feature)` instead
    """

    def __init__(self, analysis, prediction_type):
        self._internal_dict = analysis
        self.computed_as_type = analysis["computed_as_type"]
        self.modalities = [DSSSubpopulationModality(analysis["feature"], self.computed_as_type, m, prediction_type) for m in analysis.get("modalities", [])]

    def get_raw(self):
        """
        Gets the raw dictionary of the subpopulation analysis

        :rtype: dict
        """
        return self._internal_dict

    def __repr__(self):
        return "{cls}(computed_as_type={type}, feature={feature}, modalities_count={modalities_count})".format(
            cls=self.__class__.__name__,
            type=self.computed_as_type,
            feature=self._internal_dict["feature"],
            modalities_count=len(self.modalities))

    def get_computation_params(self):
        """
        Gets computation params
        """
        return {
            "nbRecords":  self._internal_dict["nbRecords"],
            "randomState":  self._internal_dict["randomState"],
            "onSample":  self._internal_dict["onSample"]
        }
    
    def list_modalities(self):
        """
        List definitions of modalities
        """
        return [m.definition for m in self.modalities]

    def get_modality_data(self, definition):
        """
        Retrieves modality from definition

        :param definition: definition of modality to retrieve. Can be:
                   * :class:`dataikuapi.dss.ml.DSSSubpopulationModalityDefinition`
                   * `dataikuapi.dss.ml.DSSSubpopulationModalityDefinition.MISSING_VALUES` 
                      to retrieve modality corresponding to missing values
                   * for category modality, can be a str corresponding to the value of the modality
                   * for numeric modality, can be a number inside the modality

        :returns: the modality
        :rtype: :class:`dataikuapi.dss.ml.DSSSubpopulationModality`
        """

        if definition == DSSSubpopulationModalityDefinition.MISSING_VALUES:
            for m in self.modalities:
                if m.definition.missing_values:
                    return m
            raise ValueError("No 'missing values' modality found")

        if isinstance(definition, DSSSubpopulationModalityDefinition):
            modality_candidates = [m for m in self.modalities if m.definition.index == definition.index]
            if len(modality_candidates) == 0:
                raise ValueError("Modality with index '%s' not found" % definition.index)
            return modality_candidates[0]
        
        for m in self.modalities:
            if m.definition.contains(definition):
                return m
        raise ValueError("Modality not found: %s" % definition)


class DSSSubpopulationAnalyses(object):
    """
    Object to read details of subpopulation analyses of a trained model

    Do not create this object directly, use :meth:`DSSTrainedPredictionModelDetails.get_subpopulation_analyses()` instead
    """

    def __init__(self, data, prediction_type):
        self._internal_dict = data
        self.prediction_type = prediction_type
        self.analyses = []
        for analysis in data.get("subpopulationAnalyses", []):
            self.analyses.append(DSSSubpopulationAnalysis(analysis, prediction_type))

    def get_raw(self):
        """
        Gets the raw dictionary of subpopulation analyses

        :rtype: dict
        """
        return self._internal_dict

    def __repr__(self):
        return "{cls}(prediction_type={type}, analyses={analyses})".format(cls=self.__class__.__name__,
                                                                           type=self.prediction_type,
                                                                           analyses=self.list_analyses())
    def get_global(self):
        """
        Retrieves information and performance on the full dataset used to compute the subpopulation analyses
        """
        return DSSSubpopulationGlobal(self._internal_dict["global"], self.prediction_type)

    def list_analyses(self):
        """
        Lists all features on which subpopulation analyses have been computed
        """
        return [analysis.get_raw()["feature"] for analysis in self.analyses]
    
    def get_analysis(self, feature):
        """
        Retrieves the subpopulation analysis for a particular feature
        """
        try:
            return next(analysis for analysis in self.analyses if analysis.get_raw()["feature"] == feature)
        except StopIteration:
            raise ValueError("Subpopulation analysis for feature '%s' cannot be found" % feature)


class DSSPartialDependence(object):
    """
    Object to read details of partial dependence of a trained model

    Do not create this object directly, use :meth:`DSSPartialDependencies.get_partial_dependence(feature)` instead
    """

    def __init__(self, data):
        self._internal_dict = data

    def get_raw(self):
        """
        Gets the raw dictionary of the partial dependence

        :rtype: dict
        """
        return self._internal_dict

    def __repr__(self):
        return "{cls}(feature={feature})".format(cls=self.__class__.__name__, feature=self._internal_dict["feature"])

    def get_computation_params(self):
        """
        Gets computation params
        """
        return {
            "nbRecords":  self._internal_dict["nbRecords"],
            "randomState":  self._internal_dict["randomState"],
            "onSample":  self._internal_dict["onSample"]
        }


class DSSPartialDependencies(object):
    """
    Object to read details of partial dependencies of a trained model

    Do not create this object directly, use :meth:`DSSTrainedPredictionModelDetails.get_partial_dependencies()` instead
    """

    def __init__(self, data):
        self._internal_dict = data
        self.partial_dependencies = []
        for pd in data.get("partialDependencies", []):
            self.partial_dependencies.append(DSSPartialDependence(pd))

    def get_raw(self):
        """
        Gets the raw dictionary of partial dependencies

        :rtype: dict
        """
        return self._internal_dict

    def __repr__(self):
        return "{cls}(features={features})".format(cls=self.__class__.__name__, features=self.list_features())

    def list_features(self):
        """
        Lists all features on which partial dependencies have been computed
        """
        return [partial_dep.get_raw()["feature"] for partial_dep in self.partial_dependencies]

    def get_partial_dependence(self, feature):
        """
        Retrieves the partial dependencies for a particular feature
        """
        try:
            return next(pd for pd in self.partial_dependencies if pd.get_raw()["feature"] == feature)
        except StopIteration:
            raise ValueError("Partial dependence for feature '%s' cannot be found" % feature)


class DSSClustersFacts(object):
    def __init__(self, clusters_facts):
        self.clusters_facts = clusters_facts

    def get_raw(self):
        """Gets the raws facts data structure"""
        return self.clusters_facts

    def get_cluster_size(self, cluster_index):
        """Gets the size of a cluster identified by its index"""
        return self.clusters_facts["clusters"][cluster_index]["size"]

    def get_facts_for_cluster(self, cluster_index):
        """
        Gets all facts for a cluster identified by its index. Returns a list of dicts

        :rtype: list
        """
        return self.clusters_facts["clusters"][cluster_index]["facts"]

    def get_facts_for_cluster_and_feature(self, cluster_index, feature_name):
        """
        Gets all facts for a cluster identified by its index, limited to a feature name. Returns a list of dicts

        :rtype: list
        """
        return [x for x in self.get_facts_for_cluster(cluster_index) if x["feature_label"] == feature_name]


class DSSTrainedClusteringModelDetails(DSSTrainedModelDetails):
    """
    Object to read details of a trained clustering model

    Do not create this object directly, use :meth:`DSSMLTask.get_trained_model_details()` instead
    """

    def __init__(self, details, snippet, saved_model=None, saved_model_version=None, mltask=None, mltask_model_id=None):
        DSSTrainedModelDetails.__init__(self, details, snippet, saved_model, saved_model_version, mltask, mltask_model_id)


    def get_raw(self):
        """
        Gets the raw dictionary of trained model details
        """
        return self.details

    def get_train_info(self):
        """
        Returns various information about the train process (size of the train set, quick description, timing information)

        :rtype: dict
        """
        return self.details["trainInfo"]

    def get_facts(self):
        """
        Gets the 'cluster facts' data, i.e. the structure behind the screen "for cluster X, average of Y is Z times higher than average

        :rtype: :class:`DSSClustersFacts`
        """
        return DSSClustersFacts(self.details["facts"])

    def get_performance_metrics(self):
        """
        Returns all performance metrics for this clustering model.
        :returns: a dict of performance metrics values
        :rtype: dict
        """
        import copy
        clean_snippet = copy.deepcopy(self.snippet)
        for x in ["fullModelId", "algorithm", "trainInfo", "userMeta", "backendType", "sessionId", "sessionDate", "facts"]:
            if x in clean_snippet:
                del clean_snippet[x]
        return clean_snippet

    def get_preprocessing_settings(self):
        """
        Gets the preprocessing settings that were used to train this model

        :rtype: dict
        """
        return self.details["preprocessing"]

    def get_modeling_settings(self):
        """
        Gets the modeling (algorithms) settings that were used to train this model.

        Note: the structure of this dict is not the same as the modeling params on the ML Task
        (which may contain several algorithm)

        :rtype: dict
        """
        return self.details["modeling"]

    def get_actual_modeling_params(self):
        """
        Gets the actual / resolved parameters that were used to train this model.
        :return: A dictionary, which contains at least a "resolved" key
        :rtype: dict
        """
        return self.details["actualParams"]

    def get_scatter_plots(self):
        """
        Gets the cluster scatter plot data 

        :return: a DSSScatterPlots object to interact with the scatter plots
        :rtype: :class:`dataikuapi.dss.ml.DSSScatterPlots`
        """
        scatters = self.mltask.client._perform_json(
            "GET", "/projects/%s/models/lab/%s/%s/models/%s/scatter-plots" % (self.mltask.project_key, self.mltask.analysis_id, self.mltask.mltask_id, self.mltask_model_id))
        return DSSScatterPlots(scatters)


class DSSMLTask(object):

    @staticmethod
    def from_full_model_id(client, fmi, project_key=None):
        match = re.match(r"^A-(\w+)-(\w+)-(\w+)-(s[0-9]+)-(pp[0-9]+(-part-(\w+)|-base)?)-(m[0-9]+)$", fmi)
        if match is None:
            return DataikuException("Invalid model id: {}".format(fmi))
        else:
            if project_key is None:
                project_key = match.group(1)
            return DSSMLTask(client, project_key, match.group(2), match.group(3))

    """A handle to interact with a MLTask for prediction or clustering in a DSS visual analysis"""
    def __init__(self, client, project_key, analysis_id, mltask_id):
        self.client = client
        self.project_key = project_key
        self.analysis_id = analysis_id
        self.mltask_id = mltask_id

    def delete(self):
        """
        Delete the present ML task
        """
        return self.client._perform_json(
                "DELETE", "/projects/%s/models/lab/%s/%s/" % (self.project_key, self.analysis_id, self.mltask_id))


    def wait_guess_complete(self):
        """
        Waits for guess to be complete. This should be called immediately after the creation of a new ML Task
        (if the ML Task was created with wait_guess_complete=False),
        before calling ``get_settings`` or ``train``
        """
        while True:
            status = self.get_status()
            if status.get("guessing", "???") == False:
                break
            time.sleep(0.2)


    def get_status(self):
        """
        Gets the status of this ML Task

        :return: a dict
        """
        return self.client._perform_json(
                "GET", "/projects/%s/models/lab/%s/%s/status" % (self.project_key, self.analysis_id, self.mltask_id))


    def get_settings(self):
        """
        Gets the settings of this ML Tasks

        :return: a DSSMLTaskSettings object to interact with the settings
        :rtype: :class:`dataikuapi.dss.ml.DSSMLTaskSettings`
        """
        settings =  self.client._perform_json(
                "GET", "/projects/%s/models/lab/%s/%s/settings" % (self.project_key, self.analysis_id, self.mltask_id))

        if settings["taskType"] == "PREDICTION":
            return DSSPredictionMLTaskSettings(self.client, self.project_key, self.analysis_id, self.mltask_id, settings)
        else:
            return DSSClusteringMLTaskSettings(self.client, self.project_key, self.analysis_id, self.mltask_id, settings)

    def train(self, session_name=None, session_description=None):
        """
        Trains models for this ML Task
        
        :param str session_name: name for the session
        :param str session_description: description for the session

        This method waits for train to complete. If you want to train asynchronously, use :meth:`start_train` and :meth:`wait_train_complete`

        This method returns the list of trained model identifiers. It returns models that have been trained  for this train
        session, not all trained models for this ML task. To get all identifiers for all models trained across all training sessions,
        use :meth:`get_trained_models_ids`

        These identifiers can be used for :meth:`get_trained_model_snippet`, :meth:`get_trained_model_details` and :meth:`deploy_to_flow`

        :return: A list of model identifiers
        :rtype: list of strings
        """
        train_ret = self.start_train(session_name, session_description)
        self.wait_train_complete()
        return self.get_trained_models_ids(session_id = train_ret["sessionId"])

    def ensemble(self, model_ids=None, method=None):
        """
        Create an ensemble model of a set of models
        
        :param list model_ids: A list of model identifiers (defaults to `[]`)
        :param str method: the ensembling method. One of: AVERAGE, PROBA_AVERAGE, MEDIAN, VOTE, LINEAR_MODEL, LOGISTIC_MODEL

        This method waits for the ensemble train to complete. If you want to train asynchronously, use :meth:`start_ensembling` and :meth:`wait_train_complete`

        This method returns the identifier of the trained ensemble.
        To get all identifiers for all models trained across all training sessions,
        use :meth:`get_trained_models_ids`

        This identifier can be used for :meth:`get_trained_model_snippet`, :meth:`get_trained_model_details` and :meth:`deploy_to_flow`

        :return: A model identifier
        :rtype: string
        """
        if model_ids is None:
            model_ids = []
        train_ret = self.start_ensembling(model_ids, method)
        self.wait_train_complete()
        return train_ret


    def start_train(self, session_name=None, session_description=None):
        """
        Starts asynchronously a new train session for this ML Task.

        :param str session_name: name for the session
        :param str session_description: description for the session

        This returns immediately, before train is complete. To wait for train to complete, use ``wait_train_complete()``
        """
        session_info = {
                            "sessionName" : session_name,
                            "sessionDescription" : session_description
                        }

        return self.client._perform_json(
                "POST", "/projects/%s/models/lab/%s/%s/train" % (self.project_key, self.analysis_id, self.mltask_id), body=session_info)


    def start_ensembling(self, model_ids=None, method=None):
        """
        Creates asynchronously a new ensemble models of a set of models.

        :param list model_ids: A list of model identifiers (defaults to `[]`)
        :param str method: the ensembling method (AVERAGE, PROBA_AVERAGE, MEDIAN, VOTE, LINEAR_MODEL, LOGISTIC_MODEL)

        This returns immediately, before train is complete. To wait for train to complete, use :meth:`wait_train_complete`

        :return: the model identifier of the ensemble
        :rtype: string
        """
        if model_ids is None:
            model_ids = []
        ensembling_request = {
                            "method" : method,
                            "modelsIds" : model_ids
                        }

        return self.client._perform_json(
                "POST", "/projects/%s/models/lab/%s/%s/ensemble" % (self.project_key, self.analysis_id, self.mltask_id), body=ensembling_request)['id']


    def wait_train_complete(self):
        """
        Waits for train to be complete (if started with :meth:`start_train`)
        """
        while True:
            status = self.get_status()
            if status.get("training", "???") == False:
                break
            time.sleep(2)


    def get_trained_models_ids(self, session_id=None, algorithm=None):
        """
        Gets the list of trained model identifiers for this ML task.

        These identifiers can be used for :meth:`get_trained_model_snippet` and :meth:`deploy_to_flow`

        :return: A list of model identifiers
        :rtype: list of strings
        """
        full_model_ids = self.get_status()["fullModelIds"]
        if session_id is not None:
            full_model_ids = [fmi for fmi in full_model_ids if fmi.get('fullModelId', {}).get('sessionId', '') == session_id]
        model_ids = [x["id"] for x in full_model_ids]
        if algorithm is not None:
            # algorithm is in the snippets
            model_ids = [fmi for fmi, s in self.get_trained_model_snippet(ids=model_ids).iteritems() if s.get("algorithm", "") == algorithm]
        return model_ids


    def get_trained_model_snippet(self, id=None, ids=None):
        """
        Gets a quick summary of a trained model, as a dict. For complete information and a structured object, use :meth:`get_trained_model_detail`

        :param str id: a model id
        :param list ids: a list of model ids

        :rtype: dict
        """
        if id is not None:
            obj = {
                "modelsIds" : [id]
            }
        elif ids is not None:
            obj = {
                "modelsIds" : ids
            }
        else:
            obj = {}

        ret = self.client._perform_json(
            "GET", "/projects/%s/models/lab/%s/%s/models-snippets" % (self.project_key, self.analysis_id, self.mltask_id),
            body = obj)
        if id is not None:
            return ret[id]
        else:
            return ret

    def get_trained_model_details(self, id):
        """
        Gets details for a trained model
        
        :param str id: Identifier of the trained model, as returned by :meth:`get_trained_models_ids`

        :return: A :class:`DSSTrainedPredictionModelDetails` or :class:`DSSTrainedClusteringModelDetails` representing the details of this trained model id
        :rtype: :class:`DSSTrainedPredictionModelDetails` or :class:`DSSTrainedClusteringModelDetails`
        """
        ret = self.client._perform_json(
            "GET", "/projects/%s/models/lab/%s/%s/models/%s/details" % (self.project_key, self.analysis_id, self.mltask_id,id))
        snippet = self.get_trained_model_snippet(id)

        if "facts" in ret:
            return DSSTrainedClusteringModelDetails(ret, snippet, mltask=self, mltask_model_id=id)
        else:
            return DSSTrainedPredictionModelDetails(ret, snippet, mltask=self, mltask_model_id=id)

    def delete_trained_model(self, model_id):
        """
        Deletes a trained model

        :param str model_id: Model identifier, as returend by :meth:`get_trained_models_ids`
        """
        self.client._perform_empty(
            "DELETE", "/projects/%s/models/lab/%s/%s/models/%s" % (self.project_key, self.analysis_id, self.mltask_id, model_id))

    def deploy_to_flow(self, model_id, model_name, train_dataset, test_dataset=None, redo_optimization=True):
        """
        Deploys a trained model from this ML Task to a saved model + train recipe in the Flow.

        :param str model_id: Model identifier, as returned by :meth:`get_trained_models_ids`
        :param str model_name: Name of the saved model to deploy in the Flow
        :param str train_dataset: Name of the dataset to use as train set. May either be a short name or a PROJECT.name long name (when using a shared dataset)
        :param str test_dataset: Name of the dataset to use as test set. If null, split will be applied to the train set. May either be a short name or a PROJECT.name long name (when using a shared dataset). Only for PREDICTION tasks
        :param bool redo_optimization: Should the hyperparameters optimization phase be done ? Defaults to True. Only for PREDICTION tasks
        :return: A dict containing: "savedModelId" and "trainRecipeName" - Both can be used to obtain further handles
        :rtype: dict
        """
        obj = {
            "trainDatasetRef" : train_dataset,
            "testDatasetRef" : test_dataset,
            "modelName" : model_name,
            "redoOptimization":  redo_optimization
        }
        return self.client._perform_json(
            "POST", "/projects/%s/models/lab/%s/%s/models/%s/actions/deployToFlow" % (self.project_key, self.analysis_id, self.mltask_id, model_id),
            body = obj)


    def redeploy_to_flow(self, model_id, recipe_name=None, saved_model_id=None, activate=True):
        """
        Redeploys a trained model from this ML Task to a saved model + train recipe in the Flow. Either 
        recipe_name of saved_model_id need to be specified

        :param str model_id: Model identifier, as returned by :meth:`get_trained_models_ids`
        :param str recipe_name: Name of the training recipe to update
        :param str saved_model_id: Name of the saved model to update
        :param bool activate: Should the deployed model version become the active version 
        :return: A dict containing: "impactsDownstream" - whether the active version changed and downstream recipes are impacted 
        :rtype: dict
        """
        obj = {
            "recipeName" : recipe_name,
            "savedModelId" : saved_model_id,
            "activate" : activate
        }
        return self.client._perform_json(
            "POST", "/projects/%s/models/lab/%s/%s/models/%s/actions/redeployToFlow" % (self.project_key, self.analysis_id, self.mltask_id, model_id),
            body = obj)

    def remove_unused_splits(self):
        """
        Deletes all stored splits data that are not anymore in use for this ML Task.

        It is generally not needed to call this method
        """
        self.client._perform_empty(
            "POST", "/projects/%s/models/lab/%s/%s/actions/removeUnusedSplits" % (self.project_key, self.analysis_id, self.mltask_id))

    def remove_all_splits(self):
        """
        Deletes all stored splits data for this ML Task. This operation saves disk space.

        After performing this operation, it will not be possible anymore to:
        * Ensemble already trained models
        * View the "predicted data" or "charts" for already trained models
        * Resume training of models for which optimization had been previously interrupted
        
        Training new models remains possible
        """
        self.client._perform_empty(
            "POST", "/projects/%s/models/lab/%s/%s/actions/removeAllSplits" % (self.project_key, self.analysis_id, self.mltask_id))

    def guess(self, prediction_type=None, reguess_level=None):
        """
        Guess the feature handling and the algorithms.
        :param string prediction_type: In case of a prediction problem the prediction type can be specify. Valid values are BINARY_CLASSIFICATION, REGRESSION, MULTICLASS.
        :param bool reguess_level: One of the following values: TARGET_CHANGE, TARGET_REGUESS and FULL_REGUESS. Only valid for prediction ML Tasks, cannot be specified if prediction_type is also set.
        """
        obj = {}
        if prediction_type is not None:
            obj["predictionType"] = prediction_type

        if reguess_level is not None:
            obj["reguessLevel"] = reguess_level

        self.client._perform_empty(
            "PUT",
            "/projects/%s/models/lab/%s/%s/guess" % (self.project_key, self.analysis_id, self.mltask_id),
            params = obj)
