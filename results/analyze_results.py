import pandas as pd
import matplotlib.pyplot as plt
import os

# Configuración de estilo
plt.style.use('ggplot')
input_dir = 'resultados-remotos'
output_dir = 'results'

def analyze_security():
    history_file = os.path.join(input_dir, 'resultado_dos_stats_history.csv')
    if not os.path.exists(history_file):
        print(f"Error: No se encontró {history_file}")
        return

    df = pd.read_csv(history_file)
    
    # Limpiar datos
    df = df[df['Total Request Count'] > 0]
    
    # Crear la figura
    plt.figure(figsize=(12, 6))
    
    # Graficar Solicitudes vs Bloqueos (Fallas)
    plt.plot(df.index, df['Requests/s'], label='Solicitudes Totales (RPS)', color='blue', linewidth=2, marker='o')
    plt.plot(df.index, df['Failures/s'], label='Solicitudes Bloqueadas (403 Forbidden)', color='red', linestyle='--', linewidth=2, marker='x')
    
    plt.title('Análisis de Seguridad: Táctica de Rate Limiting (Resultados Remotos)', fontsize=14)
    plt.xlabel('Puntos de Muestreo (Segundos)', fontsize=12)
    plt.ylabel('Peticiones por Segundo (RPS)', fontsize=12)
    plt.legend()
    plt.grid(True)
    
    # Guardar la gráfica
    plot_path = os.path.join(output_dir, 'analisis_remoto_dos.png')
    plt.savefig(plot_path)
    print(f"Gráfica guardada en: {plot_path}")

    # Análisis de métricas clave
    total_reqs = df['Total Request Count'].max()
    total_fails = df['Total Failure Count'].max()
    fail_rate = (total_fails / total_reqs) * 100 if total_reqs > 0 else 0
    
    print("\n--- RESUMEN DEL EXPERIMENTO REMOTO ---")
    print(f"Total de peticiones enviadas: {total_reqs}")
    print(f"Total de peticiones bloqueadas: {total_fails}")
    print(f"Efectividad del Bloqueo: {fail_rate:.2f}%")
    
    # Verificar si el bloqueo fue desde el inicio
    first_row_fails = df.iloc[0]['Total Failure Count']
    if first_row_fails > 0:
        print("\nOBSERVACIÓN CRÍTICA:")
        print("La IP ya estaba bloqueada antes de iniciar el test.")
        print("Esto demuestra la PERSISTENCIA de la táctica (el bloqueo sobrevive entre sesiones),")
        print("pero para ver la ACCIÓN INSTANTÁNEA (transición 200 -> 403),")
        print("debes limpiar la IP con el endpoint /unblock/ antes de correr el test.")
    
    if fail_rate > 95:
        print("\nRESULTADO: ÉXITO. El sistema denegó el acceso al atacante de forma consistente.")


def analyze_security_unblocked():
    history_file = os.path.join(input_dir, 'resultado_dos_desbl_stats_history.csv')
    if not os.path.exists(history_file):
        print(f"Error: No se encontró {history_file}")
        return

    df = pd.read_csv(history_file)
    df = df[df['Total Request Count'] > 0]
    
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['Requests/s'], label='Solicitudes Totales (RPS)', color='green', linewidth=2, marker='o')
    plt.plot(df.index, df['Failures/s'], label='Solicitudes Bloqueadas (403 Forbidden)', color='darkorange', linestyle='--', linewidth=2, marker='x')
    
    plt.title('Análisis de Seguridad: Táctica de Rate Limiting (Post-Desbloqueo)', fontsize=14)
    plt.xlabel('Puntos de Muestreo (Segundos)', fontsize=12)
    plt.ylabel('Peticiones por Segundo (RPS)', fontsize=12)
    plt.legend()
    plt.grid(True)
    
    # Nota de que se eliminó la blacklist
    plt.text(0.5, 0.01, 'Nota: Experimento ejecutado tras limpieza manual de la Blacklist (unblock_ip)', 
             horizontalalignment='center', verticalalignment='center', transform=plt.gca().transAxes,
             fontsize=10, color='gray', style='italic')
    
    plot_path = os.path.join(output_dir, 'analisis_desbloqueado_dos.png')
    plt.savefig(plot_path)
    print(f"Gráfica guardada en: {plot_path}")

    total_reqs = df['Total Request Count'].max()
    total_fails = df['Total Failure Count'].max()
    print("\n--- RESUMEN DEL EXPERIMENTO (POST-DESBLOQUEO) ---")
    print(f"Total de peticiones: {total_reqs}")
    print(f"Total de bloqueos: {total_fails}")
    
    # Comprobar si realmente hubo una fase de éxito
    if total_fails == total_reqs:
        print("OBSERVACIÓN: A pesar del intento de desbloqueo, el sistema registró bloqueos desde el primer segundo.")
        print("Causa probable: El tráfico inicial (50 usuarios) superó el umbral de 100 peticiones en menos de 1 segundo.")

def analyze_block_curve():
    history_file = os.path.join(input_dir, 'curva_bloqueo_stats_history.csv')
    if not os.path.exists(history_file):
        print(f"Error: No se encontró {history_file}")
        return

    df = pd.read_csv(history_file)
    df = df[df['Total Request Count'] > 0]
    
    # Calcular Peticiones Exitosas Acumuladas
    df['Successful_Requests'] = df['Total Request Count'] - df['Total Failure Count']
    
    plt.figure(figsize=(12, 6))
    
    # Graficar Peticiones Exitosas vs Fallidas Acumuladas
    plt.plot(df.index, df['Successful_Requests'], label='Peticiones Exitosas (Acumuladas)', color='green', linewidth=3)
    plt.plot(df.index, df['Total Failure Count'], label='Peticiones Bloqueadas (Acumuladas)', color='red', linewidth=3)
    
    # Línea de umbral (100 peticiones)
    plt.axhline(y=100, color='black', linestyle=':', label='Umbral de Bloqueo (100 reqs)')
    
    # Encontrar el punto exacto de la transición para poner una flecha
    transition_idx = df[df['Total Failure Count'] > 0].index[0]
    plt.annotate('Táctica Activada', xy=(transition_idx, 100), xytext=(transition_idx-5, 500),
                 arrowprops=dict(facecolor='black', shrink=0.05),
                 fontsize=12, fontweight='bold')

    plt.title('Curva de Bloqueo: Transición de Acceso Permitido a Denegado', fontsize=14)
    plt.xlabel('Puntos de Muestreo (Segundos)', fontsize=12)
    plt.ylabel('Cantidad de Peticiones', fontsize=12)
    plt.legend()
    plt.grid(True)
    
    plot_path = os.path.join(output_dir, 'curva_bloqueo_transicion.png')
    plt.savefig(plot_path)
    print(f"Gráfica guardada en: {plot_path}")

    # Análisis final
    max_success = df['Successful_Requests'].max()
    print("\n--- ANÁLISIS DE LA CURVA DE BLOQUEO ---")
    print(f"Peticiones permitidas antes del bloqueo: {max_success}")
    print(f"Umbral configurado en código: 100")
    print(f"Precisión de la táctica: {100 - abs(100-max_success):.1f}%")
    print("RESULTADO: LA GRÁFICA MUESTRA EL 'CODO' DONDE EL SISTEMA CIERRA LA PUERTA.")

if __name__ == "__main__":
    analyze_security()
    analyze_security_unblocked()
    analyze_block_curve()
