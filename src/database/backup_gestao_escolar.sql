-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: gestao_escolar
-- ------------------------------------------------------
-- Server version	8.0.45-0ubuntu0.22.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `aulas`
--

DROP TABLE IF EXISTS `aulas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `aulas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `escola_id` int NOT NULL,
  `turma_id` int NOT NULL,
  `professor_id` int NOT NULL,
  `disciplina_id` int NOT NULL,
  `dia` varchar(20) NOT NULL,
  `periodo` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_aulas_turma_slot` (`turma_id`,`dia`,`periodo`),
  UNIQUE KEY `uq_aulas_professor_slot` (`professor_id`,`dia`,`periodo`),
  KEY `fk_aulas_escola` (`escola_id`),
  KEY `fk_aulas_disciplina` (`disciplina_id`),
  CONSTRAINT `fk_aulas_disciplina` FOREIGN KEY (`disciplina_id`) REFERENCES `disciplinas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_aulas_escola` FOREIGN KEY (`escola_id`) REFERENCES `escolas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_aulas_professor` FOREIGN KEY (`professor_id`) REFERENCES `professores` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_aulas_turma` FOREIGN KEY (`turma_id`) REFERENCES `turmas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3637 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `aulas`
--

LOCK TABLES `aulas` WRITE;
/*!40000 ALTER TABLE `aulas` DISABLE KEYS */;
INSERT INTO `aulas` VALUES (69,2,3,2,6,'Terça',4),(70,2,3,2,7,'Segunda',3),(71,2,3,2,7,'Quinta',1),(72,2,3,2,7,'Quarta',3),(73,2,3,2,7,'Quarta',5),(74,2,3,2,7,'Terça',1),(75,2,3,2,4,'Terça',5),(76,2,3,2,4,'Segunda',5),(77,2,3,2,4,'Quarta',2),(78,2,3,2,4,'Quarta',4),(79,2,3,1,6,'Quinta',5),(80,2,3,1,6,'Sexta',2),(81,2,3,1,6,'Quinta',3),(82,2,3,1,6,'Sexta',1),(83,2,3,1,6,'Segunda',4),(84,2,3,1,6,'Sexta',5),(85,2,3,1,6,'Segunda',1),(86,2,3,1,6,'Quinta',2),(87,2,2,2,3,'Segunda',1),(88,2,1,2,3,'Terça',3),(89,2,1,2,6,'Segunda',4),(90,2,1,2,7,'Quarta',1),(91,2,1,2,4,'Terça',2),(92,2,4,4,3,'Quarta',4),(93,2,4,4,3,'Sexta',3),(94,2,4,4,3,'Quarta',6),(95,2,4,4,3,'Segunda',2),(96,2,4,4,3,'Quinta',1),(97,2,4,4,3,'Quarta',3),(98,2,4,4,3,'Segunda',6),(99,2,4,4,3,'Sexta',6),(100,2,4,4,3,'Quinta',2),(101,2,4,4,3,'Sexta',1),(3422,4,8,12,10,'Terça',3),(3423,4,8,12,10,'Sexta',3),(3424,4,8,12,10,'Sexta',5),(3425,4,8,12,10,'Segunda',5),(3426,4,8,12,28,'Quinta',5),(3427,4,8,6,12,'Quarta',3),(3428,4,8,6,12,'Terça',2),(3429,4,8,6,18,'Segunda',4),(3430,4,8,6,18,'Segunda',2),(3431,4,8,15,14,'Terça',5),(3432,4,8,15,14,'Sexta',4),(3433,4,8,5,9,'Quarta',5),(3434,4,8,5,9,'Terça',1),(3435,4,8,9,17,'Quinta',2),(3436,4,8,9,17,'Sexta',1),(3437,4,8,7,16,'Quarta',4),(3438,4,8,7,13,'Sexta',2),(3439,4,8,20,11,'Segunda',3),(3440,4,8,20,11,'Quarta',2),(3441,4,8,20,11,'Segunda',1),(3442,4,8,20,11,'Quinta',4),(3443,4,8,14,19,'Quinta',3),(3444,4,8,16,32,'Quinta',1),(3445,4,8,21,15,'Quarta',1),(3446,4,8,21,15,'Terça',4),(3447,4,5,10,24,'Segunda',5),(3448,4,5,10,24,'Sexta',1),(3449,4,5,10,26,'Segunda',1),(3450,4,5,10,30,'Sexta',4),(3451,4,5,10,27,'Quarta',6),(3452,4,5,10,25,'Segunda',2),(3453,4,5,10,29,'Sexta',5),(3454,4,5,12,10,'Quarta',4),(3455,4,5,12,10,'Quinta',6),(3456,4,5,12,10,'Quarta',3),(3457,4,5,12,40,'Sexta',6),(3458,4,5,6,18,'Terça',5),(3459,4,5,6,18,'Segunda',6),(3460,4,5,15,14,'Terça',1),(3461,4,5,15,14,'Terça',2),(3462,4,5,5,9,'Terça',6),(3463,4,5,5,9,'Quinta',2),(3464,4,5,9,17,'Terça',4),(3465,4,5,9,17,'Segunda',4),(3466,4,5,7,13,'Quarta',2),(3467,4,5,13,15,'Quinta',1),(3468,4,5,7,16,'Quinta',4),(3469,4,5,11,11,'Quinta',3),(3470,4,5,11,11,'Quinta',5),(3471,4,5,11,11,'Sexta',2),(3472,4,5,11,11,'Quarta',5),(3473,4,5,14,19,'Quarta',1),(3474,4,5,16,32,'Terça',3),(3475,4,5,8,12,'Sexta',3),(3476,4,5,8,12,'Segunda',3),(3477,4,9,17,11,'Segunda',2),(3478,4,9,17,11,'Quarta',1),(3479,4,9,17,11,'Terça',4),(3480,4,9,17,11,'Quarta',4),(3481,4,9,12,10,'Quinta',2),(3482,4,9,12,10,'Sexta',2),(3483,4,9,12,10,'Sexta',1),(3484,4,9,12,10,'Segunda',4),(3485,4,9,6,18,'Segunda',5),(3486,4,9,6,18,'Quinta',5),(3487,4,9,15,14,'Quarta',5),(3488,4,9,15,14,'Quinta',3),(3489,4,9,5,9,'Quarta',3),(3490,4,9,5,9,'Terça',3),(3491,4,9,9,17,'Terça',5),(3492,4,9,9,17,'Sexta',5),(3493,4,9,13,15,'Terça',2),(3494,4,9,13,15,'Segunda',1),(3495,4,9,7,13,'Sexta',3),(3496,4,9,7,16,'Sexta',4),(3497,4,9,11,12,'Terça',1),(3498,4,9,11,12,'Segunda',3),(3499,4,9,20,41,'Quinta',1),(3500,4,9,16,32,'Quinta',4),(3501,4,9,14,19,'Quarta',2),(3502,4,6,10,23,'Terça',6),(3503,4,6,10,23,'Segunda',3),(3504,4,6,10,20,'Quinta',5),(3505,4,6,10,20,'Sexta',2),(3506,4,6,10,33,'Quinta',6),(3507,4,6,10,33,'Terça',1),(3508,4,6,10,21,'Segunda',4),(3509,4,6,10,21,'Quarta',3),(3510,4,6,10,22,'Terça',5),(3511,4,6,17,11,'Sexta',1),(3512,4,6,17,11,'Sexta',6),(3513,4,6,17,11,'Terça',3),(3514,4,6,17,11,'Quarta',2),(3515,4,6,12,10,'Terça',4),(3516,4,6,12,10,'Quarta',6),(3517,4,6,12,10,'Terça',2),(3518,4,6,12,34,'Sexta',4),(3519,4,6,12,34,'Segunda',6),(3520,4,6,12,35,'Quinta',1),(3521,4,6,6,18,'Quarta',4),(3522,4,6,6,18,'Quarta',5),(3523,4,6,15,14,'Quinta',2),(3524,4,6,15,14,'Quinta',4),(3525,4,6,15,36,'Quarta',1),(3526,4,6,9,17,'Segunda',1),(3527,4,6,9,17,'Sexta',3),(3528,4,6,5,9,'Segunda',2),(3529,4,6,5,9,'Quinta',3),(3530,4,6,13,15,'Sexta',5),(3531,4,6,8,12,'Segunda',5),(3532,4,10,17,11,'Quinta',5),(3533,4,10,17,11,'Quinta',1),(3534,4,10,17,11,'Segunda',5),(3535,4,10,17,11,'Sexta',5),(3536,4,10,12,10,'Segunda',1),(3537,4,10,12,10,'Quarta',1),(3538,4,10,12,10,'Segunda',2),(3539,4,10,12,10,'Quinta',4),(3540,4,10,6,18,'Terça',1),(3541,4,10,6,18,'Terça',3),(3542,4,10,15,14,'Segunda',4),(3543,4,10,15,14,'Quarta',2),(3544,4,10,9,17,'Terça',2),(3545,4,10,9,17,'Sexta',2),(3546,4,10,5,9,'Segunda',3),(3547,4,10,5,9,'Terça',5),(3548,4,10,13,15,'Quarta',5),(3549,4,10,13,15,'Sexta',3),(3550,4,10,7,16,'Quarta',3),(3551,4,10,7,13,'Quinta',3),(3552,4,10,11,12,'Quarta',4),(3553,4,10,11,12,'Terça',4),(3554,4,10,20,41,'Sexta',4),(3555,4,10,14,19,'Sexta',1),(3556,4,10,16,32,'Quinta',2),(3557,4,11,17,11,'Quinta',4),(3558,4,11,17,11,'Sexta',3),(3559,4,11,17,11,'Quarta',5),(3560,4,11,17,11,'Segunda',3),(3561,4,11,6,18,'Quinta',1),(3562,4,11,6,18,'Quarta',2),(3563,4,11,6,12,'Sexta',2),(3564,4,11,6,12,'Sexta',4),(3565,4,11,15,14,'Segunda',2),(3566,4,11,15,14,'Segunda',5),(3567,4,11,9,17,'Quinta',3),(3568,4,11,9,17,'Quarta',1),(3569,4,11,5,9,'Sexta',5),(3570,4,11,5,9,'Quinta',5),(3571,4,11,13,15,'Quarta',4),(3572,4,11,13,15,'Terça',5),(3573,4,11,7,13,'Segunda',1),(3574,4,11,7,16,'Terça',1),(3575,4,11,18,10,'Sexta',1),(3576,4,11,18,10,'Segunda',4),(3577,4,11,18,10,'Terça',3),(3578,4,11,18,10,'Terça',2),(3579,4,11,20,41,'Quarta',3),(3580,4,11,16,32,'Terça',4),(3581,4,11,14,19,'Quinta',2),(3582,4,7,10,39,'Quarta',5),(3583,4,7,10,39,'Quarta',1),(3584,4,7,10,39,'Terça',3),(3585,4,7,10,37,'Sexta',3),(3586,4,7,10,37,'Quarta',4),(3587,4,7,10,40,'Segunda',6),(3588,4,7,10,40,'Terça',2),(3589,4,7,10,31,'Quarta',2),(3590,4,7,10,31,'Quinta',4),(3591,4,7,10,20,'Quinta',1),(3592,4,7,17,11,'Terça',5),(3593,4,7,17,11,'Quinta',2),(3594,4,7,17,11,'Sexta',4),(3595,4,7,17,11,'Segunda',1),(3596,4,7,6,18,'Segunda',3),(3597,4,7,6,18,'Quinta',3),(3598,4,7,6,12,'Sexta',5),(3599,4,7,15,14,'Sexta',6),(3600,4,7,15,14,'Sexta',2),(3601,4,7,15,38,'Terça',4),(3602,4,7,9,17,'Segunda',5),(3603,4,7,9,17,'Terça',1),(3604,4,7,5,9,'Sexta',1),(3605,4,7,5,9,'Segunda',4),(3606,4,7,13,15,'Segunda',2),(3607,4,7,13,15,'Terça',6),(3608,4,7,18,10,'Quinta',6),(3609,4,7,18,10,'Quarta',3),(3610,4,7,18,10,'Quarta',6),(3611,4,7,19,36,'Quinta',5),(3612,4,12,17,11,'Quinta',3),(3613,4,12,17,11,'Segunda',4),(3614,4,12,17,11,'Terça',1),(3615,4,12,17,11,'Quarta',3),(3616,4,12,12,41,'Quarta',5),(3617,4,12,6,12,'Terça',4),(3618,4,12,6,12,'Quinta',4),(3619,4,12,6,18,'Sexta',3),(3620,4,12,6,18,'Quinta',2),(3621,4,12,15,14,'Quinta',1),(3622,4,12,15,14,'Segunda',1),(3623,4,12,9,17,'Quarta',2),(3624,4,12,9,17,'Segunda',2),(3625,4,12,5,9,'Terça',2),(3626,4,12,5,9,'Segunda',5),(3627,4,12,13,15,'Sexta',4),(3628,4,12,13,15,'Sexta',1),(3629,4,12,7,13,'Terça',5),(3630,4,12,7,16,'Segunda',3),(3631,4,12,18,10,'Quarta',1),(3632,4,12,18,10,'Sexta',5),(3633,4,12,18,10,'Sexta',2),(3634,4,12,18,10,'Quinta',5),(3635,4,12,16,32,'Quarta',4),(3636,4,12,14,19,'Terça',3);
/*!40000 ALTER TABLE `aulas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `disciplinas`
--

DROP TABLE IF EXISTS `disciplinas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `disciplinas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `escola_id` int NOT NULL,
  `nome` varchar(255) NOT NULL,
  `cor` varchar(20) NOT NULL DEFAULT '#22c55e',
  PRIMARY KEY (`id`),
  KEY `fk_disciplinas_escola` (`escola_id`),
  CONSTRAINT `fk_disciplinas_escola` FOREIGN KEY (`escola_id`) REFERENCES `escolas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=42 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `disciplinas`
--

LOCK TABLES `disciplinas` WRITE;
/*!40000 ALTER TABLE `disciplinas` DISABLE KEYS */;
INSERT INTO `disciplinas` VALUES (3,2,'Banco de Dados','#22c55e'),(4,2,'Matemática','#22c55e'),(5,2,'Portugues','#84cc16'),(6,2,'Rede de computadores','#22c55e'),(7,2,'Execução de Projetos','#3b82f6'),(9,4,'Física','#22c55e'),(10,4,'Matemática','#3b82f6'),(11,4,'Português','#a855f7'),(12,4,'Biologia','#f97316'),(13,4,'Filosofia','#ef4444'),(14,4,'História','#eab308'),(15,4,'Inglês','#ec4899'),(16,4,'Sociologia','#06b6d4'),(17,4,'Geografia','#84cc16'),(18,4,'Química','#6366f1'),(19,4,'Educação Física','#7d0000'),(20,4,'POO','#2e46ff'),(21,4,'LLP','#362bff'),(22,4,'HD','#3b29ff'),(23,4,'PW','#2a26ff'),(24,4,'FA','#3429ff'),(25,4,'FMT','#3430ff'),(26,4,'PI','#3c36ff'),(27,4,'LE','#3936ff'),(28,4,'ENEM','#22c55e'),(29,4,'GP','#3d2bff'),(30,4,'ME','#3d33ff'),(31,4,'AS','#4930ff'),(32,4,'Artes','#06b6d4'),(33,4,'BD','#4a3dff'),(34,4,'FF','#ec4899'),(35,4,'LA','#ec4899'),(36,4,'MA','#eab308'),(37,4,'AUD','#3b82f6'),(38,4,'EMP','#22c55e'),(39,4,'PC','#3b82f6'),(40,4,'RE','#3b82f6'),(41,4,'FIC','#06b6d4');
/*!40000 ALTER TABLE `disciplinas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `escolas`
--

DROP TABLE IF EXISTS `escolas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `escolas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `nome` varchar(255) NOT NULL,
  `criado_em` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_escolas_usuario_nome` (`user_id`,`nome`),
  KEY `idx_escolas_user_id` (`user_id`),
  CONSTRAINT `fk_escolas_usuario` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `escolas`
--

LOCK TABLES `escolas` WRITE;
/*!40000 ALTER TABLE `escolas` DISABLE KEYS */;
INSERT INTO `escolas` VALUES (2,1,'Escola Teste','2026-04-24 14:31:32'),(4,2,'Dom Pedro II','2026-04-28 00:18:26');
/*!40000 ALTER TABLE `escolas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `professores`
--

DROP TABLE IF EXISTS `professores`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `professores` (
  `id` int NOT NULL AUTO_INCREMENT,
  `escola_id` int NOT NULL,
  `nome` varchar(255) NOT NULL,
  `disciplina_id` int NOT NULL,
  `max_aulas_semana` int NOT NULL DEFAULT '10',
  `dias_disponiveis` text NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_professores_escola` (`escola_id`),
  KEY `fk_professores_disciplina` (`disciplina_id`),
  CONSTRAINT `fk_professores_disciplina` FOREIGN KEY (`disciplina_id`) REFERENCES `disciplinas` (`id`),
  CONSTRAINT `fk_professores_escola` FOREIGN KEY (`escola_id`) REFERENCES `escolas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `professores`
--

LOCK TABLES `professores` WRITE;
/*!40000 ALTER TABLE `professores` DISABLE KEYS */;
INSERT INTO `professores` VALUES (1,2,'Francismar',6,10,'Segunda,Quinta,Sexta'),(2,2,'Guilherme',3,23,'Segunda,Terça,Quarta'),(4,2,'Haynan',3,10,'Segunda,Quarta,Quinta,Sexta'),(5,4,'JOSE',9,16,'Segunda,Terça,Quarta,Quinta,Sexta'),(6,4,'JULIANA',12,23,'Segunda,Terça,Quarta,Quinta,Sexta'),(7,4,'RENATO',13,12,'Segunda,Terça,Quarta,Quinta,Sexta'),(8,4,'LUCIENE',12,3,'Segunda,Terça,Quarta,Quinta,Sexta'),(9,4,'GEOVANE',17,16,'Segunda,Terça,Quarta,Quinta,Sexta'),(10,4,'GUILHERME',20,26,'Segunda,Terça,Quarta,Quinta,Sexta'),(11,4,'GEISSIANY',11,8,'Segunda,Terça,Quarta,Quinta,Sexta'),(12,4,'KENIA',10,24,'Segunda,Terça,Quarta,Quinta,Sexta'),(13,4,'RAQUEL',15,12,'Segunda,Terça,Quarta,Quinta,Sexta'),(14,4,'LUANA',19,6,'Segunda,Terça,Quarta,Quinta,Sexta'),(15,4,'MARLUS',14,18,'Segunda,Terça,Quarta,Quinta,Sexta'),(16,4,'ROGERIO',32,6,'Segunda,Terça,Quarta,Quinta,Sexta'),(17,4,'ANALICE',11,24,'Segunda,Terça,Quarta,Quinta,Sexta'),(18,4,'CLÁUDIO',10,11,'Segunda,Terça,Quarta,Quinta,Sexta'),(19,4,'DIVINO',36,1,'Segunda,Terça,Quarta,Quinta,Sexta'),(20,4,'ELICA',11,7,'Segunda,Terça,Quarta,Quinta,Sexta'),(21,4,'ISMÊNIA',15,2,'Segunda,Terça,Quarta,Quinta,Sexta');
/*!40000 ALTER TABLE `professores` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `professores_cargas`
--

DROP TABLE IF EXISTS `professores_cargas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `professores_cargas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `professor_id` int NOT NULL,
  `turma_id` int NOT NULL,
  `disciplina_id` int NOT NULL,
  `aulas_semana` int NOT NULL DEFAULT '1',
  `criado_em` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_professores_cargas` (`professor_id`,`turma_id`,`disciplina_id`),
  KEY `fk_professores_cargas_turma` (`turma_id`),
  KEY `fk_professores_cargas_disciplina` (`disciplina_id`),
  CONSTRAINT `fk_professores_cargas_disciplina` FOREIGN KEY (`disciplina_id`) REFERENCES `disciplinas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_professores_cargas_professor` FOREIGN KEY (`professor_id`) REFERENCES `professores` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_professores_cargas_turma` FOREIGN KEY (`turma_id`) REFERENCES `turmas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=529 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `professores_cargas`
--

LOCK TABLES `professores_cargas` WRITE;
/*!40000 ALTER TABLE `professores_cargas` DISABLE KEYS */;
INSERT INTO `professores_cargas` VALUES (1,2,3,3,2,'2026-04-26 20:32:48'),(2,2,3,7,5,'2026-04-26 20:32:48'),(3,2,3,4,4,'2026-04-26 20:32:48'),(4,2,3,5,1,'2026-04-26 20:32:48'),(5,2,3,6,1,'2026-04-26 20:32:48'),(6,2,2,3,1,'2026-04-26 20:32:48'),(7,2,2,7,1,'2026-04-26 20:32:48'),(8,2,2,4,1,'2026-04-26 20:32:48'),(9,2,2,5,1,'2026-04-26 20:32:48'),(10,2,2,6,1,'2026-04-26 20:32:48'),(11,2,1,3,1,'2026-04-26 20:32:49'),(12,2,1,7,1,'2026-04-26 20:32:49'),(13,2,1,4,1,'2026-04-26 20:32:49'),(14,2,1,5,1,'2026-04-26 20:32:49'),(15,2,1,6,1,'2026-04-26 20:32:49'),(16,1,3,6,10,'2026-04-26 20:33:00'),(17,4,4,3,10,'2026-04-26 20:44:04'),(106,19,7,36,1,'2026-04-28 02:25:57'),(174,21,8,15,2,'2026-04-28 02:31:09'),(264,11,5,11,4,'2026-04-28 02:44:22'),(265,11,9,12,2,'2026-04-28 02:44:22'),(266,11,10,12,2,'2026-04-28 02:44:22'),(361,7,8,13,1,'2026-04-28 02:50:47'),(362,7,8,16,1,'2026-04-28 02:50:47'),(363,7,5,13,1,'2026-04-28 02:50:47'),(364,7,5,16,1,'2026-04-28 02:50:47'),(365,7,9,13,1,'2026-04-28 02:50:47'),(366,7,9,16,1,'2026-04-28 02:50:47'),(367,7,10,13,1,'2026-04-28 02:50:47'),(368,7,10,16,1,'2026-04-28 02:50:47'),(369,7,11,13,1,'2026-04-28 02:50:47'),(370,7,11,16,1,'2026-04-28 02:50:47'),(371,7,12,13,1,'2026-04-28 02:50:47'),(372,7,12,16,1,'2026-04-28 02:50:47'),(385,18,11,10,4,'2026-04-28 02:51:13'),(386,18,7,10,3,'2026-04-28 02:51:13'),(387,18,12,10,4,'2026-04-28 02:51:13'),(388,5,8,9,2,'2026-04-28 02:51:28'),(389,5,5,9,2,'2026-04-28 02:51:28'),(390,5,9,9,2,'2026-04-28 02:51:28'),(391,5,6,9,2,'2026-04-28 02:51:28'),(392,5,10,9,2,'2026-04-28 02:51:28'),(393,5,11,9,2,'2026-04-28 02:51:28'),(394,5,7,9,2,'2026-04-28 02:51:28'),(395,5,12,9,2,'2026-04-28 02:51:28'),(396,17,9,11,4,'2026-04-28 02:51:39'),(397,17,6,11,4,'2026-04-28 02:51:39'),(398,17,10,11,4,'2026-04-28 02:51:39'),(399,17,11,11,4,'2026-04-28 02:51:39'),(400,17,7,11,4,'2026-04-28 02:51:39'),(401,17,12,11,4,'2026-04-28 02:51:40'),(418,9,8,17,2,'2026-04-28 02:53:07'),(419,9,5,17,2,'2026-04-28 02:53:07'),(420,9,9,17,2,'2026-04-28 02:53:07'),(421,9,6,17,2,'2026-04-28 02:53:07'),(422,9,10,17,2,'2026-04-28 02:53:07'),(423,9,11,17,2,'2026-04-28 02:53:07'),(424,9,7,17,2,'2026-04-28 02:53:07'),(425,9,12,17,2,'2026-04-28 02:53:07'),(426,16,8,32,1,'2026-04-28 02:53:43'),(427,16,5,32,1,'2026-04-28 02:53:43'),(428,16,9,32,1,'2026-04-28 02:53:43'),(429,16,10,32,1,'2026-04-28 02:53:43'),(430,16,11,32,1,'2026-04-28 02:53:43'),(431,16,12,32,1,'2026-04-28 02:53:43'),(462,20,8,11,4,'2026-04-29 01:18:37'),(463,20,9,41,1,'2026-04-29 01:18:37'),(464,20,10,41,1,'2026-04-29 01:18:37'),(465,20,11,41,1,'2026-04-29 01:18:37'),(466,10,5,24,2,'2026-04-29 01:24:58'),(467,10,5,25,1,'2026-04-29 01:24:58'),(468,10,5,29,1,'2026-04-29 01:24:58'),(469,10,5,27,1,'2026-04-29 01:24:58'),(470,10,5,30,1,'2026-04-29 01:24:58'),(471,10,5,26,1,'2026-04-29 01:24:58'),(472,10,6,33,2,'2026-04-29 01:24:58'),(473,10,6,22,1,'2026-04-29 01:24:58'),(474,10,6,21,2,'2026-04-29 01:24:58'),(475,10,6,20,2,'2026-04-29 01:24:58'),(476,10,6,23,2,'2026-04-29 01:24:58'),(477,10,7,31,2,'2026-04-29 01:24:58'),(478,10,7,37,2,'2026-04-29 01:24:58'),(479,10,7,39,3,'2026-04-29 01:24:58'),(480,10,7,20,1,'2026-04-29 01:24:58'),(481,10,7,40,2,'2026-04-29 01:24:58'),(482,6,8,12,2,'2026-04-29 01:27:54'),(483,6,8,18,2,'2026-04-29 01:27:54'),(484,6,5,18,2,'2026-04-29 01:27:54'),(485,6,9,18,2,'2026-04-29 01:27:54'),(486,6,6,18,2,'2026-04-29 01:27:54'),(487,6,10,18,2,'2026-04-29 01:27:54'),(488,6,11,12,2,'2026-04-29 01:27:54'),(489,6,11,18,2,'2026-04-29 01:27:54'),(490,6,7,12,1,'2026-04-29 01:27:54'),(491,6,7,18,2,'2026-04-29 01:27:54'),(492,6,12,12,2,'2026-04-29 01:27:54'),(493,6,12,18,2,'2026-04-29 01:27:54'),(494,12,8,28,1,'2026-04-29 01:32:25'),(495,12,8,10,4,'2026-04-29 01:32:25'),(496,12,5,10,3,'2026-04-29 01:32:25'),(497,12,5,40,1,'2026-04-29 01:32:25'),(498,12,9,10,4,'2026-04-29 01:32:25'),(499,12,6,34,2,'2026-04-29 01:32:25'),(500,12,6,35,1,'2026-04-29 01:32:25'),(501,12,6,10,3,'2026-04-29 01:32:25'),(502,12,10,10,4,'2026-04-29 01:32:25'),(503,12,12,41,1,'2026-04-29 01:32:25'),(504,14,8,19,1,'2026-04-29 01:33:12'),(505,14,5,19,1,'2026-04-29 01:33:12'),(506,14,9,19,1,'2026-04-29 01:33:12'),(507,14,10,19,1,'2026-04-29 01:33:12'),(508,14,11,19,1,'2026-04-29 01:33:12'),(509,14,12,19,1,'2026-04-29 01:33:12'),(510,8,5,12,2,'2026-04-29 01:33:47'),(511,8,6,12,1,'2026-04-29 01:33:47'),(512,15,8,14,2,'2026-04-29 01:35:42'),(513,15,5,14,2,'2026-04-29 01:35:42'),(514,15,9,14,2,'2026-04-29 01:35:42'),(515,15,6,14,2,'2026-04-29 01:35:42'),(516,15,6,36,1,'2026-04-29 01:35:42'),(517,15,10,14,2,'2026-04-29 01:35:42'),(518,15,11,14,2,'2026-04-29 01:35:42'),(519,15,7,38,1,'2026-04-29 01:35:42'),(520,15,7,14,2,'2026-04-29 01:35:42'),(521,15,12,14,2,'2026-04-29 01:35:42'),(522,13,5,15,1,'2026-04-29 01:36:54'),(523,13,9,15,2,'2026-04-29 01:36:54'),(524,13,6,15,1,'2026-04-29 01:36:54'),(525,13,10,15,2,'2026-04-29 01:36:54'),(526,13,11,15,2,'2026-04-29 01:36:54'),(527,13,7,15,2,'2026-04-29 01:36:54'),(528,13,12,15,2,'2026-04-29 01:36:54');
/*!40000 ALTER TABLE `professores_cargas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `professores_disciplinas`
--

DROP TABLE IF EXISTS `professores_disciplinas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `professores_disciplinas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `professor_id` int NOT NULL,
  `disciplina_id` int NOT NULL,
  `criado_em` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_professores_disciplinas` (`professor_id`,`disciplina_id`),
  KEY `fk_professores_disciplinas_disciplina` (`disciplina_id`),
  CONSTRAINT `fk_professores_disciplinas_disciplina` FOREIGN KEY (`disciplina_id`) REFERENCES `disciplinas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_professores_disciplinas_professor` FOREIGN KEY (`professor_id`) REFERENCES `professores` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=265 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `professores_disciplinas`
--

LOCK TABLES `professores_disciplinas` WRITE;
/*!40000 ALTER TABLE `professores_disciplinas` DISABLE KEYS */;
INSERT INTO `professores_disciplinas` VALUES (16,2,3,'2026-04-26 20:32:48'),(17,2,4,'2026-04-26 20:32:48'),(18,2,5,'2026-04-26 20:32:48'),(19,2,6,'2026-04-26 20:32:48'),(20,2,7,'2026-04-26 20:32:48'),(21,1,6,'2026-04-26 20:33:00'),(24,4,3,'2026-04-26 20:44:04'),(95,19,36,'2026-04-28 02:25:57'),(141,21,15,'2026-04-28 02:31:09'),(174,11,11,'2026-04-28 02:44:22'),(175,11,12,'2026-04-28 02:44:22'),(197,7,13,'2026-04-28 02:50:47'),(198,7,16,'2026-04-28 02:50:47'),(201,18,10,'2026-04-28 02:51:13'),(202,5,9,'2026-04-28 02:51:28'),(203,17,11,'2026-04-28 02:51:39'),(210,9,17,'2026-04-28 02:53:07'),(211,16,32,'2026-04-28 02:53:43'),(234,20,11,'2026-04-29 01:18:37'),(235,20,41,'2026-04-29 01:18:37'),(236,10,20,'2026-04-29 01:24:58'),(237,10,21,'2026-04-29 01:24:58'),(238,10,22,'2026-04-29 01:24:58'),(239,10,23,'2026-04-29 01:24:58'),(240,10,24,'2026-04-29 01:24:58'),(241,10,25,'2026-04-29 01:24:58'),(242,10,26,'2026-04-29 01:24:58'),(243,10,27,'2026-04-29 01:24:58'),(244,10,29,'2026-04-29 01:24:58'),(245,10,30,'2026-04-29 01:24:58'),(246,10,31,'2026-04-29 01:24:58'),(247,10,33,'2026-04-29 01:24:58'),(248,10,37,'2026-04-29 01:24:58'),(249,10,39,'2026-04-29 01:24:58'),(250,10,40,'2026-04-29 01:24:58'),(251,6,12,'2026-04-29 01:27:54'),(252,6,18,'2026-04-29 01:27:54'),(253,12,10,'2026-04-29 01:32:25'),(254,12,28,'2026-04-29 01:32:25'),(255,12,34,'2026-04-29 01:32:25'),(256,12,35,'2026-04-29 01:32:25'),(257,12,40,'2026-04-29 01:32:25'),(258,12,41,'2026-04-29 01:32:25'),(259,14,19,'2026-04-29 01:33:12'),(260,8,12,'2026-04-29 01:33:47'),(261,15,14,'2026-04-29 01:35:42'),(262,15,36,'2026-04-29 01:35:42'),(263,15,38,'2026-04-29 01:35:42'),(264,13,15,'2026-04-29 01:36:54');
/*!40000 ALTER TABLE `professores_disciplinas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `professores_turmas`
--

DROP TABLE IF EXISTS `professores_turmas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `professores_turmas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `professor_id` int NOT NULL,
  `turma_id` int NOT NULL,
  `criado_em` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_professores_turmas` (`professor_id`,`turma_id`),
  KEY `fk_professores_turmas_turma` (`turma_id`),
  CONSTRAINT `fk_professores_turmas_professor` FOREIGN KEY (`professor_id`) REFERENCES `professores` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_professores_turmas_turma` FOREIGN KEY (`turma_id`) REFERENCES `turmas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=394 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `professores_turmas`
--

LOCK TABLES `professores_turmas` WRITE;
/*!40000 ALTER TABLE `professores_turmas` DISABLE KEYS */;
INSERT INTO `professores_turmas` VALUES (26,2,1,'2026-04-26 20:32:48'),(27,2,2,'2026-04-26 20:32:48'),(28,2,3,'2026-04-26 20:32:48'),(29,1,3,'2026-04-26 20:33:00'),(30,4,4,'2026-04-26 20:44:04'),(86,19,7,'2026-04-28 02:25:57'),(117,21,8,'2026-04-28 02:31:09'),(188,11,5,'2026-04-28 02:44:22'),(189,11,9,'2026-04-28 02:44:22'),(190,11,10,'2026-04-28 02:44:22'),(273,7,5,'2026-04-28 02:50:47'),(274,7,8,'2026-04-28 02:50:47'),(275,7,9,'2026-04-28 02:50:47'),(276,7,10,'2026-04-28 02:50:47'),(277,7,11,'2026-04-28 02:50:47'),(278,7,12,'2026-04-28 02:50:47'),(287,18,7,'2026-04-28 02:51:13'),(288,18,11,'2026-04-28 02:51:13'),(289,18,12,'2026-04-28 02:51:13'),(290,5,5,'2026-04-28 02:51:28'),(291,5,6,'2026-04-28 02:51:28'),(292,5,7,'2026-04-28 02:51:28'),(293,5,8,'2026-04-28 02:51:28'),(294,5,9,'2026-04-28 02:51:28'),(295,5,10,'2026-04-28 02:51:28'),(296,5,11,'2026-04-28 02:51:28'),(297,5,12,'2026-04-28 02:51:28'),(298,17,6,'2026-04-28 02:51:39'),(299,17,7,'2026-04-28 02:51:39'),(300,17,9,'2026-04-28 02:51:39'),(301,17,10,'2026-04-28 02:51:39'),(302,17,11,'2026-04-28 02:51:39'),(303,17,12,'2026-04-28 02:51:39'),(317,9,5,'2026-04-28 02:53:07'),(318,9,6,'2026-04-28 02:53:07'),(319,9,7,'2026-04-28 02:53:07'),(320,9,8,'2026-04-28 02:53:07'),(321,9,9,'2026-04-28 02:53:07'),(322,9,10,'2026-04-28 02:53:07'),(323,9,11,'2026-04-28 02:53:07'),(324,9,12,'2026-04-28 02:53:07'),(325,16,5,'2026-04-28 02:53:43'),(326,16,8,'2026-04-28 02:53:43'),(327,16,9,'2026-04-28 02:53:43'),(328,16,10,'2026-04-28 02:53:43'),(329,16,11,'2026-04-28 02:53:43'),(330,16,12,'2026-04-28 02:53:43'),(350,20,8,'2026-04-29 01:18:37'),(351,20,9,'2026-04-29 01:18:37'),(352,20,10,'2026-04-29 01:18:37'),(353,20,11,'2026-04-29 01:18:37'),(354,10,5,'2026-04-29 01:24:58'),(355,10,6,'2026-04-29 01:24:58'),(356,10,7,'2026-04-29 01:24:58'),(357,6,5,'2026-04-29 01:27:54'),(358,6,6,'2026-04-29 01:27:54'),(359,6,7,'2026-04-29 01:27:54'),(360,6,8,'2026-04-29 01:27:54'),(361,6,9,'2026-04-29 01:27:54'),(362,6,10,'2026-04-29 01:27:54'),(363,6,11,'2026-04-29 01:27:54'),(364,6,12,'2026-04-29 01:27:54'),(365,12,5,'2026-04-29 01:32:25'),(366,12,6,'2026-04-29 01:32:25'),(367,12,8,'2026-04-29 01:32:25'),(368,12,9,'2026-04-29 01:32:25'),(369,12,10,'2026-04-29 01:32:25'),(370,12,12,'2026-04-29 01:32:25'),(371,14,5,'2026-04-29 01:33:12'),(372,14,8,'2026-04-29 01:33:12'),(373,14,9,'2026-04-29 01:33:12'),(374,14,10,'2026-04-29 01:33:12'),(375,14,11,'2026-04-29 01:33:12'),(376,14,12,'2026-04-29 01:33:12'),(377,8,5,'2026-04-29 01:33:47'),(378,8,6,'2026-04-29 01:33:47'),(379,15,5,'2026-04-29 01:35:42'),(380,15,6,'2026-04-29 01:35:42'),(381,15,7,'2026-04-29 01:35:42'),(382,15,8,'2026-04-29 01:35:42'),(383,15,9,'2026-04-29 01:35:42'),(384,15,10,'2026-04-29 01:35:42'),(385,15,11,'2026-04-29 01:35:42'),(386,15,12,'2026-04-29 01:35:42'),(387,13,5,'2026-04-29 01:36:54'),(388,13,6,'2026-04-29 01:36:54'),(389,13,7,'2026-04-29 01:36:54'),(390,13,9,'2026-04-29 01:36:54'),(391,13,10,'2026-04-29 01:36:54'),(392,13,11,'2026-04-29 01:36:54'),(393,13,12,'2026-04-29 01:36:54');
/*!40000 ALTER TABLE `professores_turmas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `turmas`
--

DROP TABLE IF EXISTS `turmas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `turmas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `escola_id` int NOT NULL,
  `nome` varchar(255) NOT NULL,
  `aulas_por_dia` int NOT NULL DEFAULT '5',
  PRIMARY KEY (`id`),
  KEY `fk_turmas_escola` (`escola_id`),
  CONSTRAINT `fk_turmas_escola` FOREIGN KEY (`escola_id`) REFERENCES `escolas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `turmas`
--

LOCK TABLES `turmas` WRITE;
/*!40000 ALTER TABLE `turmas` DISABLE KEYS */;
INSERT INTO `turmas` VALUES (1,2,'9 A',5),(2,2,'8 A',5),(3,2,'7 A',5),(4,2,'1° EM',6),(5,4,'1 AD',6),(6,4,'2 ATI',6),(7,4,'3 ATI',6),(8,4,'1 A',5),(9,4,'2 A',5),(10,4,'2 B',5),(11,4,'3 A',5),(12,4,'3 B',5);
/*!40000 ALTER TABLE `turmas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `usuarios`
--

DROP TABLE IF EXISTS `usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `senha_hash` varchar(255) NOT NULL,
  `role` varchar(30) NOT NULL DEFAULT 'funcionario',
  `email_verificado` tinyint(1) NOT NULL DEFAULT '0',
  `email_verificado_em` timestamp NULL DEFAULT NULL,
  `token_version` int NOT NULL DEFAULT '0',
  `tentativas_login_falhas` int NOT NULL DEFAULT '0',
  `bloqueado_ate` timestamp NULL DEFAULT NULL,
  `ultimo_login_em` timestamp NULL DEFAULT NULL,
  `criado_em` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usuarios`
--

LOCK TABLES `usuarios` WRITE;
/*!40000 ALTER TABLE `usuarios` DISABLE KEYS */;
INSERT INTO `usuarios` VALUES (1,'Tecnico','admin@escola.com','scrypt:32768:8:1$suKvk6pKXETZbcwU$b898b9df824963f4922c8d01680849a34ae58295c98826b5fe0d30b80c81aecbdae381b4aa9547705fd2ade0ea2bf5e759180b5f43521fc5be1631d5beee212a','administrador',1,'2026-04-23 22:19:05',0,0,NULL,'2026-04-28 22:31:07','2026-04-23 22:19:05'),(2,'Haynan Kerlin','haynankerlin@gmail.com','scrypt:32768:8:1$puEOvlPUAczEdJnz$cd9f9dd2f7c9da26fdcbe6cb8e5f818b336d46a1d78c525dd4b8169d80d3dac817103985d7dc8320baaa0614c364164f4494da499fedc581290c87f4e337b09f','administrador',1,'2026-04-24 17:25:53',3,0,NULL,'2026-04-28 22:22:50','2026-04-23 23:18:56'),(5,'Teste','teste@escola.com','scrypt:32768:8:1$Uh3iINcDkSpftpiM$c61f5acfa9d53a71095a60bca8f82b629f5919564730c4da1b5f53bb52482b08b4498528a66324d517f472d3c86c8716dee469178a273404a9c023f5b2216f01','funcionario',1,'2026-04-24 15:13:39',23,0,NULL,'2026-04-29 01:52:16','2026-04-24 15:13:39'),(8,'Arthur Brito','arthurbcs14@gmail.com','scrypt:32768:8:1$WswhcIYtMLfQM10D$d68d0c6172d204093caddf9180a0cb8c9105a8909d77a1b01a65c183d90a7b5e7d554fc0f3958281c40751e5564e2d9b615665c7b77121ca806c71740abbc161','administrador',1,NULL,0,0,NULL,'2026-04-27 16:31:27','2026-04-26 14:25:43'),(9,'Fellipe','fellipe270680@gmail.com','scrypt:32768:8:1$09R0ZjhSHrzjAlzS$954050af53f69833f14c37f315a43bbd532fa2c8ef47386e96b8ce8f68e693f025aaa49d015f4f20e9ae82c14792cb9fb702a54363773dc0bb3bf06bfadc1c87','funcionario',1,'2026-04-28 22:30:09',0,0,NULL,'2026-04-28 22:30:42','2026-04-28 22:29:55');
/*!40000 ALTER TABLE `usuarios` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `usuarios_escolas`
--

DROP TABLE IF EXISTS `usuarios_escolas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios_escolas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `usuario_id` int NOT NULL,
  `escola_id` int NOT NULL,
  `criado_em` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_usuarios_escolas` (`usuario_id`,`escola_id`),
  KEY `fk_usuarios_escolas_escola` (`escola_id`),
  CONSTRAINT `fk_usuarios_escolas_escola` FOREIGN KEY (`escola_id`) REFERENCES `escolas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_usuarios_escolas_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usuarios_escolas`
--

LOCK TABLES `usuarios_escolas` WRITE;
/*!40000 ALTER TABLE `usuarios_escolas` DISABLE KEYS */;
INSERT INTO `usuarios_escolas` VALUES (2,1,2,'2026-04-24 14:31:32'),(28,2,4,'2026-04-28 00:18:26'),(31,9,4,'2026-04-28 22:31:27'),(32,5,4,'2026-04-29 01:52:27');
/*!40000 ALTER TABLE `usuarios_escolas` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-29  2:17:01
