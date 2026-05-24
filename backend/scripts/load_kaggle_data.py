import sys
import os
import glob
import json
import asyncio

# /app is the backend root inside Docker
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.qdrant_service import QdrantService

async def process_file(filepath: str, service: QdrantService):
    questions = []
    print(f"Loading {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if isinstance(data, list):
                    for q in data:
                        questions.append(q)
                        if len(questions) >= 1000: break
                else:
                    questions.append(data)
                
                if len(questions) >= 1000:
                    print(f"Reached 1000 questions limit for {filepath}, stopping read.")
                    break
            except Exception as e:
                print(f"Error parsing line in {filepath}: {e}")
                pass
                
    if questions:
        # Batch insert
        batch_size = 50
        total = 0
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i+batch_size]
            count = await service.upsert_questions(batch)
            total += count
            print(f"  Inserted {total}/{len(questions)} questions from {os.path.basename(filepath)}")
    return len(questions)

async def main():
    service = QdrantService.get_instance()
    await service.init_collections()
    
    # Check if we want to clear the collection first
    if os.environ.get("CLEAR_COLLECTION") == "true":
        print("Clearing questions_bank collection...")
        try:
            service.client.delete_collection(collection_name="questions_bank")
            await service.init_collections()
        except Exception as e:
            print(f"Error clearing collection: {e}")
    
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if not os.path.exists(data_dir):
        print(f"Data directory {data_dir} not found.")
        return
        
    jsonl_files = glob.glob(os.path.join(data_dir, "*.jsonl"))
    if not jsonl_files:
        print("No .jsonl files found in data directory.")
        return
        
    total_loaded = 0
    for file in jsonl_files:
        count = await process_file(file, service)
        total_loaded += count
        
    print(f"✅ Successfully seeded {total_loaded} questions from {len(jsonl_files)} files into Qdrant.")
    
    info = service.client.get_collection("questions_bank")
    print(f"   Collection total points count: {info.points_count}")

if __name__ == "__main__":
    asyncio.run(main())
