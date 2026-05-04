import numpy as np
from sklearn.ensemble import IsolationForest
class IsolationForestDetector:
    def __init__(self,contamination=0.1,random_state=42):
        self.model=IsolationForest(n_estimators=100,contamination=contamination,random_state=random_state,n_jobs=-1)
        self.name="isolation_forest"
    def fit_predict(self,X):
        self.model.fit(X);r=self.model.score_samples(X);mn,mx=r.min(),r.max()
        return np.zeros(len(X)) if mx-mn==0 else 1-(r-mn)/(mx-mn)
