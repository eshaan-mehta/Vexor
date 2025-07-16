#!/usr/bin/env python3
"""
Machine Learning Utilities for Data Analysis

This module provides various machine learning algorithms and utilities
for data preprocessing, model training, and evaluation.

Author: AI Assistant
Date: 2024
License: MIT
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from abc import ABC, abstractmethod


class DataPreprocessor:
    """
    A comprehensive data preprocessing class for machine learning pipelines.
    
    This class handles common data preprocessing tasks including:
    - Missing value imputation
    - Feature scaling and normalization
    - Categorical encoding
    - Outlier detection and removal
    """
    
    def __init__(self, strategy: str = 'mean'):
        """
        Initialize the preprocessor with a given imputation strategy.
        
        Args:
            strategy (str): Imputation strategy ('mean', 'median', 'mode')
        """
        self.strategy = strategy
        self.scalers = {}
        self.encoders = {}
    
    def handle_missing_values(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values in the dataset using the specified strategy.
        
        Args:
            data (pd.DataFrame): Input dataset with potential missing values
            
        Returns:
            pd.DataFrame: Dataset with missing values handled
        """
        if self.strategy == 'mean':
            return data.fillna(data.mean())
        elif self.strategy == 'median':
            return data.fillna(data.median())
        elif self.strategy == 'mode':
            return data.fillna(data.mode().iloc[0])
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def detect_outliers(self, data: np.ndarray, threshold: float = 3.0) -> List[int]:
        """
        Detect outliers using the Z-score method.
        
        Args:
            data (np.ndarray): Input data array
            threshold (float): Z-score threshold for outlier detection
            
        Returns:
            List[int]: Indices of detected outliers
        """
        z_scores = np.abs((data - np.mean(data)) / np.std(data))
        return np.where(z_scores > threshold)[0].tolist()


class BaseModel(ABC):
    """
    Abstract base class for machine learning models.
    
    This class defines the interface that all ML models should implement,
    ensuring consistency across different algorithms.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.is_trained = False
        self.parameters = {}
    
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Train the model on the provided dataset.
        
        Args:
            X (np.ndarray): Feature matrix
            y (np.ndarray): Target vector
        """
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions on new data.
        
        Args:
            X (np.ndarray): Feature matrix for prediction
            
        Returns:
            np.ndarray: Predicted values
        """
        pass
    
    def get_parameters(self) -> Dict:
        """Return the model parameters."""
        return self.parameters.copy()


class LinearRegression(BaseModel):
    """
    Linear Regression implementation using normal equation method.
    
    This class implements a simple linear regression algorithm that finds
    the best-fitting line through the data points by minimizing the sum
    of squared residuals.
    """
    
    def __init__(self):
        super().__init__("Linear Regression")
        self.weights = None
        self.bias = None
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Fit the linear regression model using the normal equation.
        
        The normal equation: θ = (X^T * X)^(-1) * X^T * y
        where θ contains both weights and bias.
        """
        # Add bias term (column of ones) to feature matrix
        X_with_bias = np.column_stack([np.ones(X.shape[0]), X])
        
        # Calculate parameters using normal equation
        try:
            theta = np.linalg.inv(X_with_bias.T @ X_with_bias) @ X_with_bias.T @ y
            self.bias = theta[0]
            self.weights = theta[1:]
            self.is_trained = True
            
            # Store parameters
            self.parameters = {
                'weights': self.weights.tolist(),
                'bias': float(self.bias),
                'n_features': X.shape[1]
            }
            
        except np.linalg.LinAlgError:
            raise ValueError("Matrix is singular; cannot compute normal equation")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using the trained linear model.
        
        Formula: y_pred = X * weights + bias
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        return X @ self.weights + self.bias
    
    def calculate_mse(self, X: np.ndarray, y_true: np.ndarray) -> float:
        """
        Calculate Mean Squared Error for the model predictions.
        
        Args:
            X (np.ndarray): Feature matrix
            y_true (np.ndarray): True target values
            
        Returns:
            float: Mean squared error
        """
        y_pred = self.predict(X)
        return np.mean((y_true - y_pred) ** 2)
    
    def calculate_r2_score(self, X: np.ndarray, y_true: np.ndarray) -> float:
        """
        Calculate R-squared (coefficient of determination) score.
        
        R² = 1 - (SS_res / SS_tot)
        where SS_res is the residual sum of squares and SS_tot is the total sum of squares.
        """
        y_pred = self.predict(X)
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        return 1 - (ss_res / ss_tot)


class KMeansClustering:
    """
    K-Means clustering algorithm implementation.
    
    This class implements the classic K-means algorithm for unsupervised
    learning, which partitions data into k clusters by minimizing within-cluster
    sum of squared distances.
    """
    
    def __init__(self, k: int, max_iters: int = 100, random_state: Optional[int] = None):
        """
        Initialize K-Means clustering.
        
        Args:
            k (int): Number of clusters
            max_iters (int): Maximum number of iterations
            random_state (Optional[int]): Random seed for reproducibility
        """
        self.k = k
        self.max_iters = max_iters
        self.random_state = random_state
        self.centroids = None
        self.labels = None
        
        if random_state is not None:
            np.random.seed(random_state)
    
    def fit(self, X: np.ndarray) -> None:
        """
        Fit the K-means model to the data.
        
        Algorithm:
        1. Initialize centroids randomly
        2. Assign points to nearest centroid
        3. Update centroids to cluster means
        4. Repeat until convergence
        """
        n_samples, n_features = X.shape
        
        # Initialize centroids randomly
        self.centroids = X[np.random.choice(n_samples, self.k, replace=False)]
        
        for iteration in range(self.max_iters):
            # Assign points to nearest centroid
            distances = np.sqrt(((X - self.centroids[:, np.newaxis])**2).sum(axis=2))
            new_labels = np.argmin(distances, axis=0)
            
            # Update centroids
            new_centroids = np.array([
                X[new_labels == i].mean(axis=0) if np.sum(new_labels == i) > 0 else self.centroids[i]
                for i in range(self.k)
            ])
            
            # Check for convergence
            if np.allclose(self.centroids, new_centroids):
                print(f"Converged after {iteration + 1} iterations")
                break
                
            self.centroids = new_centroids
            self.labels = new_labels
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict cluster labels for new data points.
        """
        if self.centroids is None:
            raise ValueError("Model must be fitted before making predictions")
            
        distances = np.sqrt(((X - self.centroids[:, np.newaxis])**2).sum(axis=2))
        return np.argmin(distances, axis=0)
    
    def get_inertia(self, X: np.ndarray) -> float:
        """
        Calculate the within-cluster sum of squared distances (inertia).
        """
        if self.labels is None:
            raise ValueError("Model must be fitted first")
            
        inertia = 0
        for i in range(self.k):
            cluster_points = X[self.labels == i]
            if len(cluster_points) > 0:
                inertia += np.sum((cluster_points - self.centroids[i]) ** 2)
        return inertia


def train_test_split(X: np.ndarray, y: np.ndarray, test_size: float = 0.2, 
                    random_state: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Split dataset into training and testing sets.
    
    Args:
        X (np.ndarray): Feature matrix
        y (np.ndarray): Target vector
        test_size (float): Proportion of dataset for testing
        random_state (Optional[int]): Random seed
        
    Returns:
        Tuple containing X_train, X_test, y_train, y_test
    """
    if random_state is not None:
        np.random.seed(random_state)
    
    n_samples = X.shape[0]
    n_test = int(n_samples * test_size)
    
    # Randomly shuffle indices
    indices = np.random.permutation(n_samples)
    test_indices = indices[:n_test]
    train_indices = indices[n_test:]
    
    return X[train_indices], X[test_indices], y[train_indices], y[test_indices]


def cross_validation_score(model: BaseModel, X: np.ndarray, y: np.ndarray, 
                          cv: int = 5) -> List[float]:
    """
    Perform k-fold cross-validation and return scores.
    
    Args:
        model (BaseModel): Machine learning model to evaluate
        X (np.ndarray): Feature matrix
        y (np.ndarray): Target vector
        cv (int): Number of folds
        
    Returns:
        List[float]: Cross-validation scores
    """
    n_samples = X.shape[0]
    fold_size = n_samples // cv
    scores = []
    
    for i in range(cv):
        # Define test fold indices
        start_idx = i * fold_size
        end_idx = start_idx + fold_size if i < cv - 1 else n_samples
        
        test_indices = list(range(start_idx, end_idx))
        train_indices = [j for j in range(n_samples) if j not in test_indices]
        
        # Split data
        X_train, X_test = X[train_indices], X[test_indices]
        y_train, y_test = y[train_indices], y[test_indices]
        
        # Train and evaluate
        model.fit(X_train, y_train)
        if hasattr(model, 'calculate_r2_score'):
            score = model.calculate_r2_score(X_test, y_test)
        else:
            # For clustering or other models, implement appropriate scoring
            score = 0.0
        
        scores.append(score)
    
    return scores


if __name__ == "__main__":
    # Example usage and testing
    print("Machine Learning Utilities - Testing Suite")
    print("=" * 50)
    
    # Generate sample data for testing
    np.random.seed(42)
    X = np.random.randn(100, 3)  # 100 samples, 3 features
    y = 2 * X[:, 0] + 3 * X[:, 1] - X[:, 2] + np.random.randn(100) * 0.1
    
    # Test Linear Regression
    print("\n1. Testing Linear Regression:")
    lr_model = LinearRegression()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    lr_model.fit(X_train, y_train)
    y_pred = lr_model.predict(X_test)
    
    mse = lr_model.calculate_mse(X_test, y_test)
    r2 = lr_model.calculate_r2_score(X_test, y_test)
    
    print(f"Mean Squared Error: {mse:.4f}")
    print(f"R² Score: {r2:.4f}")
    print(f"Model Parameters: {lr_model.get_parameters()}")
    
    # Test K-Means Clustering
    print("\n2. Testing K-Means Clustering:")
    kmeans = KMeansClustering(k=3, random_state=42)
    kmeans.fit(X)
    
    inertia = kmeans.get_inertia(X)
    print(f"Within-cluster sum of squares: {inertia:.4f}")
    print(f"Final centroids shape: {kmeans.centroids.shape}")
    
    # Test Cross-Validation
    print("\n3. Testing Cross-Validation:")
    cv_scores = cross_validation_score(LinearRegression(), X, y, cv=5)
    print(f"Cross-validation scores: {[f'{score:.4f}' for score in cv_scores]}")
    print(f"Mean CV score: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores) * 2:.4f})")
    
    print("\nAll tests completed successfully!") 