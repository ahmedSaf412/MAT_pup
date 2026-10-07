import os, warnings
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import GroupKFold
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.utils import to_categorical

warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

CSV_PATH = r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\app\data\karate_normalized_base.csv"

# Same model from notebook
def build_dual_stem_model(n_upper=54, n_lower=48, seq_len=30, n_classes=3):
    inp_upper = keras.Input(shape=(seq_len, n_upper), name='upper_body')
    x_up = layers.Bidirectional(layers.LSTM(64, return_sequences=True))(inp_upper)
    x_up = layers.Dropout(0.4)(x_up)
    x_up = layers.Bidirectional(layers.LSTM(32, return_sequences=True))(x_up)

    inp_lower = keras.Input(shape=(seq_len, n_lower), name='lower_body')
    x_lo = layers.Bidirectional(layers.LSTM(64, return_sequences=True))(inp_lower)
    x_lo = layers.Dropout(0.4)(x_lo)
    x_lo = layers.Bidirectional(layers.LSTM(32, return_sequences=True))(x_lo)

    fused = layers.Concatenate(axis=-1)([x_up, x_lo])
    
    attn_out = layers.MultiHeadAttention(num_heads=4, key_dim=fused.shape[-1] // 4)(fused, fused)
    attn_out = layers.LayerNormalization()(attn_out + fused)
    attn_out = layers.Dropout(0.3)(attn_out)

    pooled = layers.GlobalAveragePooling1D()(attn_out)
    pooled = layers.Dense(64, activation='relu')(pooled)
    pooled = layers.Dropout(0.3)(pooled)
    output = layers.Dense(n_classes, activation='softmax')(pooled)

    return Model(inputs=[inp_upper, inp_lower], outputs=output)

def extract_practitioner_id(clip_id):
    parts = clip_id.split('_')
    return parts[2] if len(parts) >= 4 else "Unknown"

def main():
    print("Loading data...")
    df = pd.read_csv(CSV_PATH)
    
    le = LabelEncoder()
    df['label_enc'] = le.fit_transform(df['folder_label'])
    n_classes = len(le.classes_)

    # 1. Gather Clip-Level Metadata
    clip_meta = []
    for clip_id, group in df.groupby('clip_id'):
        clip_meta.append({
            'clip_id': clip_id,
            'label_enc': group['label_enc'].iloc[0],
            'practitioner_id': extract_practitioner_id(clip_id)
        })
    meta_df = pd.DataFrame(clip_meta)
    
    # Optional manual golden set constraint (from your request):
    # If you want to reserve specific people, you'd filter them out here first.
    # For now, we will do a true 5-fold CV over EVERYONE to see the true mean variance.

    # 2. Build Tensors function
    UPPER_FEATS = [f'{c}{i}' for i in range(11, 23) for c in ['x', 'y', 'z', 'v']] + [f'angle_{i:02d}' for i in range(8, 14)]
    LOWER_FEATS = [f'{c}{i}' for i in range(23, 33) for c in ['x', 'y', 'z', 'v']] + [f'angle_{i:02d}' for i in range(0, 8)]
    SEQ_LEN = 30

    def build_sequences(clips_list):
        sub_df = df[df['clip_id'].isin(clips_list)]
        clips = sub_df['clip_id'].unique()
        
        X_up = np.zeros((len(clips), SEQ_LEN, len(UPPER_FEATS)), dtype=np.float32)
        X_lo = np.zeros((len(clips), SEQ_LEN, len(LOWER_FEATS)), dtype=np.float32)
        y = np.zeros(len(clips), dtype=np.int32)
        
        for i, clip in enumerate(clips):
            grp = sub_df[sub_df['clip_id'] == clip].sort_values('frame_idx')
            up_frames = grp[UPPER_FEATS].values
            lo_frames = grp[LOWER_FEATS].values
            X_up[i, :len(up_frames)] = up_frames[:SEQ_LEN]
            X_lo[i, :len(lo_frames)] = lo_frames[:SEQ_LEN]
            y[i] = grp['label_enc'].iloc[0]
            
        return X_up, X_lo, to_categorical(y, n_classes)

    # 3. Setup GroupKFold (Practitioner-Disjoint)
    # This guarantees no practitioner ID appears in both Train and Test for ANY fold
    gkf = GroupKFold(n_splits=5)
    
    X_meta = meta_df['clip_id'].values
    y_meta = meta_df['label_enc'].values
    groups = meta_df['practitioner_id'].values

    accuracies = []

    print("\nStarting 5-Fold Practitioner-Disjoint Cross-Validation...\n" + "="*60)
    
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X_meta, y_meta, groups), 1):
        train_clips = X_meta[train_idx]
        test_clips  = X_meta[test_idx]
        
        train_practitioners = set(groups[train_idx])
        test_practitioners  = set(groups[test_idx])
        
        print(f"\n--- FOLD {fold} ---")
        print(f"Train set: {len(train_clips)} clips | Practitioners ({len(train_practitioners)}): {train_practitioners}")
        print(f"Test set:  {len(test_clips)} clips | Practitioners ({len(test_practitioners)}): {test_practitioners}")
        print(f"Leakage check (Train ∩ Test): {train_practitioners.intersection(test_practitioners)}")

        # Build tensors
        X_up_tr, X_lo_tr, y_tr = build_sequences(train_clips)
        X_up_te, X_lo_te, y_te = build_sequences(test_clips)

        # Train model
        model = build_dual_stem_model(n_upper=len(UPPER_FEATS), n_lower=len(LOWER_FEATS), n_classes=n_classes)
        model.compile(optimizer=keras.optimizers.Adam(1e-3), loss='categorical_crossentropy', metrics=['accuracy'])
        
        es = EarlyStopping(monitor='val_loss', patience=15, restore_best_weights=True, verbose=0)
        
        # We use the test set as validation for early stopping in CV, which is standard
        model.fit([X_up_tr, X_lo_tr], y_tr, validation_data=([X_up_te, X_lo_te], y_te), 
                  epochs=100, batch_size=32, callbacks=[es], verbose=0)
        
        # Evaluate
        _, acc = model.evaluate([X_up_te, X_lo_te], y_te, verbose=0)
        print(f"Fold {fold} Accuracy: {acc * 100:.2f}%")
        accuracies.append(acc)
        
    mean_acc = np.mean(accuracies) * 100
    std_acc = np.std(accuracies) * 100
    print("\n" + "="*60)
    print(f"FINAL 5-FOLD CV RESULT: {mean_acc:.2f}% ± {std_acc:.2f}%")

if __name__ == "__main__":
    main()
