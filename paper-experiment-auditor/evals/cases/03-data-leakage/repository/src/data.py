import numpy as np
from sklearn.preprocessing import StandardScaler


def prepare(train_x, test_x):
    scaler = StandardScaler()
    scaler.fit(np.concatenate([train_x, test_x], axis=0))
    return scaler.transform(train_x), scaler.transform(test_x)

