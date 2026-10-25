import numpy as np
from run_instance_selection import fit_model, predict_model, freeze_selection


def test_tree_recovers_opposite_specialists_and_uses_no_evaluation_labels():
    x = np.array([[v]*9 for v in range(12)])
    performances = np.array([[1.,.8]]*6+[[.7,1.]]*6)
    model = fit_model('tree_depth1',x,performances)
    assert predict_model(model,np.array([[1]*9,[10]*9]))==['nsga2','spea2']
    plan = freeze_selection([str(i) for i in range(12)],x,performances,['small','large'],np.array([[1]*9,[10]*9]))
    assert plan['primary_model']!='constant_best'
    assert plan['plans'][plan['primary_model']]=={'small':'nsga2','large':'spea2'}


def test_constant_model_preserves_the_best_training_individual():
    model = fit_model('constant_best',np.zeros((6,9)),np.array([[.9,1.]]*6))
    assert predict_model(model,np.zeros((4,9)))==['spea2']*4
