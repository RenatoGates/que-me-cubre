# R8 en la compilación de lanzamiento de ¿Qué Cubre?
# Flutter y los plugins traen sus propias reglas; aquí van las que faltan.

# Flutter referencia Play Core (componentes diferidos) aunque la app no los usa
-dontwarn com.google.android.play.core.**

# Inicio de sesión con Google (Credential Manager)
-keep class com.google.android.libraries.identity.googleid.** { *; }
-if class androidx.credentials.CredentialManager
-keep class androidx.credentials.playservices.** { *; }

# Google Play Billing
-keep class com.android.vending.billing.** { *; }

# Crashlytics: pilas legibles sin exponer más que nombres de clases y líneas
-keepattributes SourceFile,LineNumberTable
-keep public class * extends java.lang.Exception
