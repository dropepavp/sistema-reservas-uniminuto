pipeline {
    agent any

    environment {
        COMPOSE_PROJECT_NAME = "reserva_jenkins"
    }

    stages {
        stage('1. Checkout') {
            steps {
                echo 'Obteniendo el código fuente desde GitHub...'
                checkout scm
            }
        }

        stage('2. Build Containers') {
            steps {
                echo 'Construyendo y levantando los contenedores con Docker Compose...'
                sh 'docker compose down --remove-orphans || true'
                sh 'docker compose build'
                sh 'docker compose up -d'
            }
        }

        stage('3. Test & Verification') {
            steps {
                echo 'Verificando la salud de los servicios y la comunicación entre contenedores...'
                // Esperar a que la base de datos esté saludable
                sh 'sleep 5'
                sh 'docker ps'
                
                // Ejecutar el script de prueba de comunicación de ida y vuelta (Criterio 5 y 6)
                sh 'docker exec reserva_web python scripts/verify_docker_network.py'
            }
        }
    }

    post {
        success {
            echo '¡Pipeline ejecutado con éxito! Los contenedores se comunican correctamente.'
            sh 'docker compose down'
        }
        failure {
            echo 'El pipeline falló durante la compilación o las pruebas.'
            sh 'docker compose logs'
            sh 'docker compose down'
        }
    }
}
