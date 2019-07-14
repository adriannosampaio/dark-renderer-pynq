
workspace "DarkRendererBindings"
   configurations { "x32", "x64"}

project "tests"
    kind "ConsoleApp"
    language "C++"
    targetdir "../"

    filter "configurations:Debug"
        architecture "x64"
        defines { "DEBUG" }
        symbols "On"

    filter "configurations:x64"
        architecture "x64"
        defines { "NDEBUG" }
        optimize "On"

    files { "main.cpp", "tracer.cpp", "tracer.hpp"}

project "tracer"
    kind "SharedLib"
    language "C++"
    targetdir "../"

    buildoptions "-std=c++11"

    includedirs {
        "deps/pybind11/include", 
        "C:/Users/adria/AppData/Local/Continuum/anaconda3/envs/addr_python/include"}

    libdirs {
        "C:/Users/adria/AppData/Local/Continuum/anaconda3/envs/addr_python/libs"
    }

    filter {"action:vs*"}
        targetextension (".pyd")

    files { "binding.cpp", "tracer.cpp", "tracer.hpp"}

    filter "configurations:x64"
        architecture "x64"
        defines { "NDEBUG" }
        optimize "On"