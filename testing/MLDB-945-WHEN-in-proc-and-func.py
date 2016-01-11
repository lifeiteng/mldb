# This file is part of MLDB. Copyright 2015 Datacratic. All rights reserved.

import json
import datetime
import requests
import random

dataset_index = 1

def run_transform(when):
    global dataset_index
    dataset_index += 1 
    result = mldb.perform("PUT", "/v1/procedures/when_procedure", [], 
                          {
                              "type": "transform",
                              "params": {
                                  "inputData": "select * from dataset1 when " + when,
                                  "outputDataset": { "id": "dataset" + str(dataset_index), "type":"sparse.mutable" }
                              }
    })

    assert result['statusCode'] == 201, "failed to create the procedure with a WHEN clause: %s" % result['response']

    result = mldb.perform("POST", "/v1/procedures/when_procedure/runs")
    #mldb.log(result)
    assert result['statusCode'] == 201, "failed to run the procedure: %s" % result['response']

    result = mldb.perform('GET', '/v1/query', [['q', "SELECT * FROM dataset" + str(dataset_index)]])
    assert result['statusCode'] == 200, "failed to get the transformed dataset"
    rows = json.loads(result["response"])
    #mldb.log(rows)
    return rows

def run_query_function(when):
    result = mldb.perform('PUT', '/v1/functions/when_function', [], {
        'type': 'sql.query',
        'params': {
            'inputData' : {
                'from': {'id': 'dataset1'},
                'when': when,
                'where': "rowName() = '9'"
            }
        }
    })

    #mldb.log(result)
    assert result['statusCode'] == 201, 'failed to create the function: %s' % result['response']

    result = mldb.perform('GET', '/v1/functions/when_function/application', [['input', '{}']], {})
    #mldb.log(result)
    assert result['statusCode'] == 200, 'failed to apply the function: %s' % result['response']
    return json.loads(result["response"])["output"]

def train_svd(when, output_index):
    global dataset_index
    dataset_index += 1 

    svd_procedure = "/v1/procedures/when_svd"
    # svd procedure configuration
    svd_config = {
        'type' : 'svd.train',
        'params' :
	{
            "trainingData": {"from" : {"id": "svd_example"}, 
                             "when" : when
                         },
            "rowOutputDataset": {
                "id": "when_svd_row_" + str(dataset_index),
                'type': "embedding" 
            },
            "columnOutputDataset" : {
                "id": "svd_embedding_" + str(output_index),
                "type" : "embedding"
            }
	}
    }
    
    result = mldb.perform('PUT', svd_procedure, [], svd_config)
    response = json.loads(result['response'])
    msg = "Could not create the svd procedure - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert result['statusCode'] == 201, msg

    result = mldb.perform('POST', svd_procedure + '/runs')
    response = json.loads(result['response'])
    msg = "Could not train the svd procedure - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert 300 > result['statusCode'] >= 200, msg

    result = mldb.perform('GET', '/v1/query', [['q', "SELECT * FROM when_svd_row_" + str(dataset_index)]])
    response = json.loads(result['response'])
    msg = "Could not get the svd embedding output - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert result['statusCode'] == 200, msg
    return len(response[0]["columns"])
    
def load_svd_dataset():
    """A dataset with two 'time slices' 
    - a slice with independent random columns with _now_ timestamp and
    - a slice with two correlated columns with tomorrow's timestamp
    This will serve at testing if the when clause was applied correctly"""

    svd_example = mldb.create_dataset({"type": "sparse.mutable", 'id' : 'svd_example'})
    for i in range(0,100):
        val_x = random.randint(1, 1000)
        val_y = random.randint(1, 1000)
        val_z = random.randint(1, 1000)
        svd_example.record_row('row_' + str(i), [
            ['x', val_x, now], ['x', val_x, same_time_tomorrow], 
            ['y', val_y, now], ['y', 2 * val_x, same_time_tomorrow], 
            ['z', val_z, now], ['z', val_z, same_time_tomorrow]
        ])
    svd_example.commit()

def load_test_dataset():
    ds1 = mldb.create_dataset({
        'type': 'sparse.mutable',
        'id': 'dataset1'})

    row_count = 10
    for i in xrange(row_count - 1):
        # row name is x's value
        ds1.record_row(str(i), [['x', i, now], ['y', i, now]])
        
    ds1.record_row(str(row_count - 1), [['x', 9, same_time_tomorrow], ['y', 9, same_time_tomorrow]])
    ds1.commit()

def train_tsne(when):
    global dataset_index
    dataset_index += 1 

    tsne_procedure = "/v1/procedures/when_tsne"
    # t-sne procedure configuration
    tsne_config = {
        'type' : 'tsne.train',
        'params' :
	{
            "trainingData": {"from" : {"id": "svd_example"},
                                "when" : when}, 
            "rowOutputDataset": {
                "id": "tsne_embedding_" + str(dataset_index),
                'type': "embedding" 
            }
	}
    }
    
    result = mldb.perform('PUT', tsne_procedure, [], tsne_config)
    response = json.loads(result['response'])
    msg = "Could not create the t-sne procedure - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert result['statusCode'] == 201, msg

    result = mldb.perform('POST', tsne_procedure + '/runs')
    response = json.loads(result['response'])
    msg = "Could not train the t-sne procedure - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert 300 > result['statusCode'] >= 200, msg

    result = mldb.perform('GET', '/v1/query', [['q', "SELECT * FROM tsne_embedding_" + str(dataset_index)]])
    response = json.loads(result['response'])
    msg = "Could not get the t-sne embedding output - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert result['statusCode'] == 200, msg
    return len(response[0]["columns"])

def train_classifier(when):
    result = mldb.perform("PUT", "/v1/procedures/tng_classif", [], {
        "type": "classifier.train",
        "params": {
            "trainingData": { 
                "select" : "{*} as features, x as label",
                "when" : when,
                "from" : { "id": "dataset1" }
            },
            "configuration": {
                "glz": {
                    "type": "glz",
                    "verbosity": 3,
                    "normalize": True,
                    "ridge_regression": True
                }
            },
            "algorithm": "glz",
            "modelFileUrl": "file://tmp/MLDB-945.tng.cls"
        }
    })
    response = json.loads(result['response'])
    msg = "Could not create the tng classifier procedure - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert result['statusCode'] == 201, msg

    result = mldb.perform('POST', '/v1/procedures/tng_classif/runs')
    response = json.loads(result['response'])
    msg = "Could not train the tng classifier - got status {}\n{}"
    #mldb.log(response)
    msg = msg.format(result['statusCode'], response)
    assert 300 > result['statusCode'] >= 200, msg

def load_kmeans_dataset():
    """A dataset with two 'time slices' 
    - a slice with two clear clusters along the x axis _now_ timestamp and
    - a slice with two clear clusters along the y axis with tomorrow's timestamp
    This will serve at testing if the when clause was applied correctly"""

    kmeans_example = mldb.create_dataset({"type": "sparse.mutable", 'id' : 'kmeans_example'})
    for i in range(1,3):
        for j in range(0,100):
            val_x = float(random.randint(-5, 5))
            val_y = float(random.randint(-5, 5))
            row = [
                ['x', val_x + 10**i, now], ['x', val_x, same_time_tomorrow], 
                ['y', val_y, now], ['y', val_y + 10**i, same_time_tomorrow], 
            ]
            kmeans_example.record_row('row_%d_%d' % (i, j), row)
    kmeans_example.commit()

def train_kmeans(when):
    global dataset_index
    dataset_index += 1 
    
    metric = "euclidean"
    result = mldb.perform("PUT", "/v1/procedures/kmeans", [], {
        'type' : 'kmeans.train',
        'params' : {
            'trainingData' : 'select * from kmeans_example when ' + when,
            'outputDataset' : {'id' : 'kmeans_dataset_' + str(dataset_index), 'type' : 'embedding',
                        'params': { 'metric': metric }},
            'centroidsDataset' : {'id' : 'kmeans_centroids_' + str(dataset_index), 'type' : 'embedding', 
                           'params': {'metric': metric }},
            'numClusters' : 2,
            'metric': metric
        }
    })

    response = json.loads(result['response'])
    msg = "Could not create the kmeans classifier procedure - got status {}\n{}"
    msg = msg.format(result['statusCode'], response)
    assert result['statusCode'] == 201, msg

    result = mldb.perform('POST', '/v1/procedures/kmeans/runs')
    response = json.loads(result['response'])
    msg = "Could not train the kmeans cluster - got status {}\n{}"
    msg = msg.format(result['statusCode'], response)
    assert 300 > result['statusCode'] >= 200, msg

    result = mldb.perform("GET", "/v1/datasets/kmeans_centroids_%s/query" % str(dataset_index), [
        ["format", "table"], 
        ["rowNames", "true"]
    ], {})
    assert result["statusCode"] < 400, result["response"]
    kmeans_centroids = json.loads(result["response"])
    mldb.log(kmeans_centroids)
    return kmeans_centroids[1:3]


now = datetime.datetime.now()
same_time_tomorrow = now + datetime.timedelta(days=1)
in_two_hours = now + datetime.timedelta(hours=2)

load_test_dataset()
# TRANSFORM PROCEDURE
# check that the transformed dataset is as expected
for row in run_transform("timestamp() BETWEEN '2015-01-01' AND '2030-01-06'"):
    assert row["rowName"] == row["columns"][0][1], 'expected tuple matching row name %s' % row["rowName"]

# getting no tuples
for row in run_transform("timestamp() BETWEEN '2015-01-01' AND '2015-06-06'"):
    assert "columns" not in row, 'no tuple should be returned on row name %s' % row["rowName"]

# check that the last tuple is filtered out
for row in run_transform("timestamp() between '%s' and '%s'" % (now, in_two_hours)):
    if row['rowName'] is 9:
        assert 'columns' not in row, "expecting columns from row 9 to be filtered out by the when clause"

for row in run_transform("timestamp() <= '%s'" % in_two_hours):
    if row['rowName'] is 9:
        assert 'columns' not in row, "expecting columns from row 9 to be filtered out by the when clause"

# SQL.QUERY FUNCTION
output = run_query_function("timestamp() BETWEEN '2015-01-01' AND '2030-01-06'")
assert output['x'] == 9, 'expected row 9 value'

output = run_query_function("timestamp() between '%s' and '%s'" % (now, in_two_hours))
assert not output, 'expected no output'

# SVD TRAIN FUNCTION
load_svd_dataset()
assert train_svd("timestamp() > '%s'" % in_two_hours, 1) == 2, 'expected 2 independent eigenvectors - when clause might have been applied incorrectly'
assert train_svd("timestamp() < '%s'" % in_two_hours, 2) == 3, 'expected 3 independent eigenvectors - when clause might have been applied incorrectly'

# T-SNE TRAIN FUNCTION
# if t-sne is typically trained on embedding created by SVD then it is unlikely that the when clause will be useful.  In any case, this is minimal test that check that the calls do not fail
train_tsne("timestamp() > '%s'" % in_two_hours)
train_tsne("timestamp() < '%s'" % in_two_hours)

# CLASSIFIER TRAIN FUNCTION
train_classifier("timestamp() > '%s'" % in_two_hours)
train_classifier("timestamp() <= '%s'" % in_two_hours)

# KMEANS TRAIN PROCEDURE
load_kmeans_dataset()
centroids = train_kmeans("timestamp() > '%s'" % in_two_hours)
assert -1 < centroids[0][1] < 1, "was expecting the cluster to be along the x axis"

centroids = train_kmeans("timestamp() < '%s'" % in_two_hours)
assert -1 < centroids[0][2] < 1, "was expecting the cluster to be along the y axis"

mldb.script.set_return('success')
