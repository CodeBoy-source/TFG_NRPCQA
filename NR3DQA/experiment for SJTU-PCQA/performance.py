import numpy as np
import polars as pl
import argparse
import pandas as pd
import sklearn.preprocessing
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import ElasticNet, Ridge, Lasso

from sklearn.metrics import mean_squared_error
from scipy.optimize import curve_fit
from sklearn.neighbors import KNeighborsRegressor
from scipy import stats

np.random.seed(140421)

# get data according to the train test name lists, return scaled train and test set
def get_data(train_name_list,test_name_list, scaler, config):
    feature_data = pd.read_csv(config.input_dir,index_col = 0,keep_default_na=False)
    if config.merge: 
        more_feat = pd.read_csv(config.more_feat,index_col = 0,keep_default_na=False)
        feature_data = feature_data.join(more_feat, on='name', how='inner')
    feature_data = feature_data[feature_data.columns.values]
    score_data = pd.read_csv("mos.csv")
    train_set = []
    train_score = []
    test_set = []
    test_score = []
    for name in train_name_list:
        score = score_data[name].tolist()
        train_score = train_score + score
        for i in range(42):
            name_pc = name+str(i)
            data = feature_data.loc[name_pc,:].tolist()
            train_set.append(data)
    
    for name in test_name_list:
        score = score_data[name].tolist()
        test_score = test_score + score
        for i in range(42):
            name_pc = name+str(i)
            data = feature_data.loc[name_pc,:].tolist()
            test_set.append(data)
    # preprocessing      
    train_set = scaler.fit_transform(train_set)
    test_set = scaler.transform(test_set)
    return train_set,np.array(train_score)/10,test_set,np.array(test_score)/10




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=str, 
                        default='./features.csv'
                        )
    parser.add_argument('--more-feat', type=str, 
                        default='../feature_extract_pc/features/choosen_features.csv'
                        )
    parser.add_argument('--merge', action='store_true')
    config = parser.parse_args()

    cnt = 0

    valid_scalers = ["MinMaxScaler", "StandardScaler",
                     "RobustScaler", "MaxAbsScaler", 
                     "QuantileTransformer", "PowerTransformer"]


    # initialize lists to store the evaluation metrics for each fold\n",
    random_state = np.random.randint(4294967295) 
    print(random_state)
    svm = SVR(kernel="rbf")
    neigh = KNeighborsRegressor(n_neighbors=4,weights="uniform")
    clf = DecisionTreeRegressor(random_state=random_state)
    ridge = Ridge()
    
    names = ['DecisionTree', 'SVM', 'KnnRegressor', 'Ridge']
    functions = [clf,svm,neigh,ridge]
    schema =  {"function": pl.Utf8, 
                              "plcc": pl.Float64, 
                              "srocc": pl.Float64,
                              "krocc": pl.Float64,
                              "scaler":pl.Utf8}
    df = pl.DataFrame(schema=schema) 
    for scalername in valid_scalers: 
        # begin 9-folder cross data validation split
        for i in range(9):
            scaler = getattr(sklearn.preprocessing, scalername)()
            cnt =cnt+1
            train_name_list = ['redandblack','Romanoillamp','loot','soldier','ULB Unicorn','longdress','statue','shiva','hhi']
            test_name_list = [train_name_list.pop(i)]
            train_set,train_score,test_set,test_score = get_data(train_name_list,test_name_list, scaler, config)

            for i ,func in enumerate(functions): 

                func.fit(train_set, train_score) 
                predict_score = func.predict(test_set)
                # record the result
                plcc = stats.pearsonr(predict_score, test_score)[0]
                srocc = stats.spearmanr(predict_score, test_score)[0]
                krocc = stats.kendalltau(predict_score, test_score)[0]

                df = pl.concat([df, pl.DataFrame({'function':names[i], 'plcc': plcc,
                                          'srocc': srocc, 'krocc': krocc,
                                          'scaler': scalername}, 
                               schema=schema)])

    thresh = 1
    df = df.filter(
        pl.sum(
            pl.exclude(['function', 'scaler']).is_not_null() & pl.exclude(['function', 'scaler']).is_not_nan()
        ) >= thresh
    )
    groups = df.groupby(['function', 'scaler']).agg(pl.mean(['plcc','srocc','krocc'])).sort(pl.exclude(['function', 'scaler']))
    with pl.Config(tbl_rows=-1):
        print(groups)
