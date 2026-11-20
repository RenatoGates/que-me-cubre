import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Firebase (solo Crashlytics) se activa si está app/google-services.json, que no va al repositorio.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
    apply(plugin = "com.google.firebase.crashlytics")
}

// La llave de subida a Play vive fuera del repositorio, en android/key.properties.
val llave = Properties().apply {
    val archivo = rootProject.file("key.properties")
    if (archivo.exists()) archivo.inputStream().use { load(it) }
}

android {
    namespace = "com.renatogates.quecubre"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.renatogates.quecubre"
        minSdk = 24 // Android 7.0
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (llave.isNotEmpty()) {
            create("subida") {
                keyAlias = llave["keyAlias"] as String
                keyPassword = llave["keyPassword"] as String
                storeFile = file(llave["storeFile"] as String)
                storePassword = llave["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            // Sin key.properties se firma con la llave de depuración: sirve para probar el APK, no para Play.
            signingConfig = if (llave.isNotEmpty()) signingConfigs.getByName("subida") else signingConfigs.getByName("debug")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
