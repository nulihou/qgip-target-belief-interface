
import carla
import time

HOST = "localhost"
PORT = 2000

def reset():
    print("Connecting to CARLA...")
    try:
        client = carla.Client(HOST, PORT)
        client.set_timeout(5.0)
        world = client.get_world()
        
        print("Disabling Synchronous Mode...")
        settings = world.get_settings()
        settings.synchronous_mode = False
        settings.fixed_delta_seconds = None
        world.apply_settings(settings)
        print("Synchronous Mode Disabled.")
        
        # Cleanup actors?
        # Maybe better to just let the next script handle it, 
        # but ensuring sync mode is off is crucial if the server is stuck.
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset()
