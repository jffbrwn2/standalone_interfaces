# Validation Interface

A standalone web interface for validating LLM transition predictions.

## Quick Start with Docker (Recommended)

**Prerequisites:** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

1. **Setup folders and data:**
   ```bash
   mkdir data results
   # Copy your validation data file to the data folder
   cp your_validation_data.json data/validation_data.json
   ```

2. **Run the validation interface:**
   ```bash
   # Set your name for the session
   export SESSION_NAME="your_name"
   
   # Start the interface
   docker-compose up
   ```

3. **Use the interface:**
   - Open http://localhost:5001 in your browser
   - Validate predictions and provide ratings
   - Results are automatically saved to the `results/` folder

4. **Send back results:**
   - Zip the `results/` folder and send it back
   - Or upload `results/` to shared drive/GitHub

## Alternative: Manual Installation

If you prefer not to use Docker:

```bash
pip install -r requirements.txt
python validation_interface.py --data-file your_data.json --session-name your_name
```

## Configuration Options

You can customize the Docker setup with environment variables:

```bash
# Set session name and random seed
export SESSION_NAME="jane_doe"
export RANDOM_SEED=123
docker-compose up
```

## Data Format

Your JSON file should contain transitions with this structure:

```json
{
  "comparisons": [
    {
      "transition_id": "unique_id",
      "action": {"name": "action_name", "parameters": {...}},
      "input_materials": [...],
      "input_observations": [...],
      "predictions": [
        {
          "llm_provider": "model_name",
          "prediction": {
            "new_materials": [...],
            "new_observations": [...],
            "reasoning": "..."
          }
        }
      ]
    }
  ]
}
```