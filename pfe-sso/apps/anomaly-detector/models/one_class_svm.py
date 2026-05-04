import numpy as np
from sklearn.svm import OneClassSVM
class OneClassSVMDetector:
    def __init__(self,kernel="rbf",nu=0.1,gamma="scale"):
        self.model=OneClassSVM(kernel=kernel,nu=nu,gamma=gamma);self.name="one_class_svm"
    def fit_predict(self,X):
        self.model.fit(X);r=self.model.decision_function(X);mn,mx=r.min(),r.max()
        return np.zeros(len(X)) if mx-mn==0 else 1-(r-mn)/(mx-mn)
