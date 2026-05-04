import numpy as np,os
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
class AutoEncoderDetector:
    def __init__(self,contamination=0.1): self.contamination=contamination;self.model=None;self.name="autoencoder"
    def fit_predict(self,X):
        try:
            from pyod.models.auto_encoder import AutoEncoder
            nf=X.shape[1];h=max(nf*2,8);e=max(nf//2,2)
            self.model=AutoEncoder(hidden_neurons=[h,e,e,h],epochs=50,batch_size=min(32,len(X)),contamination=self.contamination,verbose=0)
            self.model.fit(X);r=self.model.decision_scores_;mn,mx=r.min(),r.max()
            return np.zeros(len(X)) if mx-mn==0 else (r-mn)/(mx-mn)
        except ImportError:
            print("  ! PyOD unavailable, fallback IF")
            from sklearn.ensemble import IsolationForest
            fb=IsolationForest(contamination=self.contamination,random_state=42);fb.fit(X);r=fb.score_samples(X);mn,mx=r.min(),r.max()
            return np.zeros(len(X)) if mx-mn==0 else 1-(r-mn)/(mx-mn)
        except Exception as e: print(f"  ! AE error: {e}");return np.zeros(len(X))
